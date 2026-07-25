"""
Structural Analysis Module - Implementation of Martínez's Paper.

This module implements the complete methodology for music structure detection:
1. Self-Similarity Matrix (SSM) generation
2. Novelty Score computation using Foote's kernel
3. Section boundary detection
4. Hierarchical clustering for section grouping
5. Structure visualization

Reference: "Detección de estructuras musicales utilizando análisis de señales 
           y representaciones visuales" - Leonel Sebastián Martínez (2023)
"""

import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

try:
    import librosa
    from scipy import signal
    from scipy.ndimage import uniform_filter1d, gaussian_filter1d
    from scipy.spatial.distance import cdist, pdist, squareform
    from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
    from sklearn.metrics import silhouette_score
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy/sklearn not available for structural analysis")

from app.services.audio_features import AudioData, AudioFeatureExtractor, audio_extractor


@dataclass
class Section:
    """Represents a detected section in the music."""
    start_time: float
    end_time: float
    start_frame: int
    end_frame: int
    cluster_id: int = -1
    label: str = ""
    features: Optional[np.ndarray] = None
    loudness: float = 0.0
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class StructuralAnalysis:
    """Complete structural analysis results."""
    # Self-similarity matrices
    ssm_spectrogram: Optional[np.ndarray] = None
    ssm_chromagram: Optional[np.ndarray] = None
    ssm_combined: Optional[np.ndarray] = None
    ssm_reduced: Optional[np.ndarray] = None  # Reduced resolution for visualization
    
    # Novelty curves
    novelty_spectrogram: Optional[np.ndarray] = None
    novelty_chromagram: Optional[np.ndarray] = None
    novelty_combined: Optional[np.ndarray] = None
    
    # Detected boundaries and sections
    boundary_frames: Optional[np.ndarray] = None
    boundary_times: Optional[np.ndarray] = None
    sections: List[Section] = field(default_factory=list)
    
    # Clustering results
    n_clusters: int = 0
    cluster_labels: Optional[np.ndarray] = None
    silhouette_score: float = 0.0
    
    # Section features for clustering
    section_features: Optional[np.ndarray] = None
    
    # Metadata
    duration: float = 0.0
    n_frames: int = 0
    hop_length: int = 512
    sample_rate: int = 22050


class SelfSimilarityMatrix:
    """
    Self-Similarity Matrix (SSM) generator.
    
    The SSM compares each frame of the audio against all other frames,
    creating a symmetric matrix where similar sections appear as blocks
    along the diagonal.
    
    Mathematical formulation:
        SSM[i,j] = similarity(feature_vector[i], feature_vector[j])
    
    Where similarity can be:
        - Cosine similarity: dot(v1, v2) / (||v1|| * ||v2||)
        - Euclidean distance: ||v1 - v2||
        - Correlation coefficient
    """
    
    @staticmethod
    def compute(
        features: np.ndarray,
        metric: str = "cosine",
        normalize: bool = True
    ) -> np.ndarray:
        """
        Compute self-similarity matrix from feature matrix.
        
        Args:
            features: Feature matrix (n_features x n_frames)
            metric: Distance metric ('cosine', 'euclidean', 'correlation')
            normalize: Whether to normalize the result to [0, 1]
        
        Returns:
            SSM matrix (n_frames x n_frames)
        """
        if not SCIPY_AVAILABLE:
            logger.error("scipy required for SSM computation")
            return np.array([])
        
        # Transpose to (n_frames x n_features) for cdist
        features_T = features.T
        
        # Compute pairwise distances
        if metric == "cosine":
            # Cosine distance = 1 - cosine_similarity
            distances = cdist(features_T, features_T, metric="cosine")
            # Convert to similarity
            ssm = 1 - distances
        elif metric == "correlation":
            distances = cdist(features_T, features_T, metric="correlation")
            ssm = 1 - distances
        else:  # euclidean
            distances = cdist(features_T, features_T, metric="euclidean")
            # Normalize and invert
            if distances.max() > 0:
                ssm = 1 - (distances / distances.max())
            else:
                ssm = np.ones_like(distances)
        
        # Handle NaN values
        ssm = np.nan_to_num(ssm, nan=0.0)
        
        # Normalize to [0, 1]
        if normalize:
            ssm_min = ssm.min()
            ssm_max = ssm.max()
            if ssm_max > ssm_min:
                ssm = (ssm - ssm_min) / (ssm_max - ssm_min)
        
        return ssm
    
    @staticmethod
    def reduce_resolution(
        ssm: np.ndarray,
        target_size: int = 200,
        method: str = "mean"
    ) -> np.ndarray:
        """
        Reduce SSM resolution by averaging blocks.
        
        This is useful for visualization and faster processing,
        as mentioned in the paper where 1-second blocks are used.
        
        Args:
            ssm: Original SSM matrix
            target_size: Target dimension
            method: Reduction method ('mean', 'max')
        
        Returns:
            Reduced SSM matrix
        """
        n = ssm.shape[0]
        if n <= target_size:
            return ssm
        
        block_size = n // target_size
        reduced_size = n // block_size
        
        # Reshape and reduce
        reduced = np.zeros((reduced_size, reduced_size))
        
        for i in range(reduced_size):
            for j in range(reduced_size):
                block = ssm[
                    i * block_size:(i + 1) * block_size,
                    j * block_size:(j + 1) * block_size
                ]
                if method == "max":
                    reduced[i, j] = np.max(block)
                else:
                    reduced[i, j] = np.mean(block)
        
        return reduced
    
    @staticmethod
    def combine_ssm(
        ssm_list: List[np.ndarray],
        weights: Optional[List[float]] = None
    ) -> np.ndarray:
        """
        Combine multiple SSMs with optional weights.
        
        Args:
            ssm_list: List of SSM matrices (same size)
            weights: Optional weights for each SSM
        
        Returns:
            Combined SSM matrix
        """
        if not ssm_list:
            return np.array([])
        
        if weights is None:
            weights = [1.0 / len(ssm_list)] * len(ssm_list)
        
        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        
        combined = np.zeros_like(ssm_list[0])
        for ssm, weight in zip(ssm_list, weights):
            combined += weight * ssm
        
        return combined


class NoveltyDetector:
    """
    Novelty Score computation using Foote's checkerboard kernel.
    
    The novelty score detects boundaries between sections by sliding
    a checkerboard kernel along the diagonal of the SSM.
    
    Mathematical formulation:
        novelty[t] = sum(kernel * SSM[t-k:t+k, t-k:t+k])
    
    Where kernel is a checkerboard pattern with Gaussian taper:
        kernel = checkerboard * gaussian_2d
    
    Reference: Foote, J. (2000). "Automatic audio segmentation using 
               a measure of audio novelty"
    """
    
    @staticmethod
    def create_checkerboard_kernel(size: int, sigma: float = 0.5) -> np.ndarray:
        """
        Create a checkerboard kernel with Gaussian taper.
        
        The kernel has the pattern:
            [+1, -1]
            [-1, +1]
        
        With Gaussian weighting to emphasize the center.
        
        Args:
            size: Kernel size (must be even)
            sigma: Gaussian sigma as fraction of size
        
        Returns:
            Checkerboard kernel matrix
        """
        if size % 2 != 0:
            size += 1
        
        half = size // 2
        
        # Create checkerboard pattern
        kernel = np.ones((size, size))
        kernel[:half, :half] = 1    # Top-left: +1
        kernel[half:, half:] = 1    # Bottom-right: +1
        kernel[:half, half:] = -1   # Top-right: -1
        kernel[half:, :half] = -1   # Bottom-left: -1
        
        # Create Gaussian taper
        x = np.linspace(-1, 1, size)
        y = np.linspace(-1, 1, size)
        X, Y = np.meshgrid(x, y)
        gaussian = np.exp(-(X**2 + Y**2) / (2 * sigma**2))
        
        # Apply Gaussian taper
        kernel = kernel * gaussian
        
        return kernel
    
    @staticmethod
    def compute_novelty(
        ssm: np.ndarray,
        kernel_size: int = 64,
        sigma: float = 0.5
    ) -> np.ndarray:
        """
        Compute novelty score by convolving kernel along SSM diagonal.
        
        Args:
            ssm: Self-similarity matrix
            kernel_size: Size of the checkerboard kernel
            sigma: Gaussian sigma for kernel taper
        
        Returns:
            Novelty score array (length = n_frames)
        """
        if not SCIPY_AVAILABLE:
            logger.error("scipy required for novelty computation")
            return np.array([])
        
        n = ssm.shape[0]
        
        # Adjust kernel size if necessary
        kernel_size = min(kernel_size, n // 4)
        if kernel_size < 4:
            kernel_size = 4
        
        # Create kernel
        kernel = NoveltyDetector.create_checkerboard_kernel(kernel_size, sigma)
        half_k = kernel_size // 2
        
        # Compute novelty by sliding kernel along diagonal
        novelty = np.zeros(n)
        
        for i in range(half_k, n - half_k):
            # Extract region around diagonal point
            region = ssm[i - half_k:i + half_k, i - half_k:i + half_k]
            
            # Compute correlation with kernel
            if region.shape == kernel.shape:
                novelty[i] = np.sum(region * kernel)
        
        # Normalize
        novelty = np.abs(novelty)
        if novelty.max() > 0:
            novelty = novelty / novelty.max()
        
        # Smooth the novelty curve
        novelty = gaussian_filter1d(novelty, sigma=kernel_size // 8)
        
        return novelty
    
    @staticmethod
    def find_boundaries(
        novelty: np.ndarray,
        threshold: float = 0.4,
        min_distance: int = 10
    ) -> np.ndarray:
        """
        Find section boundaries from novelty peaks.
        
        Args:
            novelty: Novelty score array
            threshold: Minimum peak height (0-1)
            min_distance: Minimum frames between peaks
        
        Returns:
            Array of boundary frame indices
        """
        if not SCIPY_AVAILABLE:
            logger.error("scipy required for peak detection")
            return np.array([])
        
        # Find peaks
        peaks, properties = signal.find_peaks(
            novelty,
            height=threshold,
            distance=min_distance,
            prominence=0.1
        )
        
        # Always include start and end
        boundaries = np.concatenate([[0], peaks, [len(novelty) - 1]])
        boundaries = np.unique(boundaries)
        
        return boundaries


class SectionClusterer:
    """
    Hierarchical Agglomerative Clustering for section grouping.
    
    Groups similar sections together to identify repeated parts
    (verse, chorus, bridge, etc.)
    
    Uses Ward linkage with Euclidean distance as recommended in the paper.
    """
    
    @staticmethod
    def extract_section_features(
        chromagram: np.ndarray,
        spectrogram: np.ndarray,
        boundaries: np.ndarray
    ) -> np.ndarray:
        """
        Extract feature vectors for each section.
        
        For each section, compute the mean of chromagram and spectrogram
        features, creating a compact representation.
        
        Args:
            chromagram: Chromagram matrix (12 x n_frames)
            spectrogram: Spectrogram matrix (n_bins x n_frames)
            boundaries: Section boundary indices
        
        Returns:
            Feature matrix (n_sections x n_features)
        """
        n_sections = len(boundaries) - 1
        
        # Features: chroma (12) + reduced spectrogram (16 bands)
        n_spec_bands = 16
        features = np.zeros((n_sections, 12 + n_spec_bands))
        
        # Reduce spectrogram to fewer bands
        n_bins = spectrogram.shape[0]
        band_size = n_bins // n_spec_bands
        
        for i in range(n_sections):
            start = boundaries[i]
            end = boundaries[i + 1]
            
            # Chroma features (mean over section)
            features[i, :12] = np.mean(chromagram[:, start:end], axis=1)
            
            # Spectrogram features (mean over section, reduced bands)
            for j in range(n_spec_bands):
                band_start = j * band_size
                band_end = min((j + 1) * band_size, n_bins)
                features[i, 12 + j] = np.mean(
                    spectrogram[band_start:band_end, start:end]
                )
        
        # Normalize features
        for j in range(features.shape[1]):
            col = features[:, j]
            if col.std() > 0:
                features[:, j] = (col - col.mean()) / col.std()
        
        return features
    
    @staticmethod
    def cluster_sections(
        features: np.ndarray,
        min_clusters: int = 3,
        max_clusters: int = 10
    ) -> Tuple[np.ndarray, int, float]:
        """
        Perform hierarchical clustering on section features.
        
        Uses Ward linkage with Euclidean distance.
        Optimal number of clusters determined by Silhouette score.
        
        Args:
            features: Section feature matrix
            min_clusters: Minimum number of clusters
            max_clusters: Maximum number of clusters
        
        Returns:
            Tuple of (cluster_labels, n_clusters, silhouette_score)
        """
        if not SCIPY_AVAILABLE:
            logger.error("scipy required for clustering")
            return np.array([]), 0, 0.0
        
        n_sections = features.shape[0]
        
        # Adjust cluster range based on number of sections
        min_clusters = max(2, min(min_clusters, n_sections - 1))
        max_clusters = min(max_clusters, n_sections - 1)
        
        if min_clusters >= max_clusters:
            max_clusters = min_clusters + 1
        
        # Perform hierarchical clustering
        linkage_matrix = linkage(features, method="ward", metric="euclidean")
        
        # Find optimal number of clusters using Silhouette score
        best_score = -1
        best_n = min_clusters
        best_labels = None
        
        for n in range(min_clusters, max_clusters + 1):
            labels = fcluster(linkage_matrix, n, criterion="maxclust")
            
            # Need at least 2 clusters for silhouette
            if len(np.unique(labels)) >= 2:
                try:
                    score = silhouette_score(features, labels)
                    if score > best_score:
                        best_score = score
                        best_n = n
                        best_labels = labels
                except:
                    pass
        
        if best_labels is None:
            best_labels = fcluster(linkage_matrix, min_clusters, criterion="maxclust")
            best_n = min_clusters
            best_score = 0.0
        
        # Convert to 0-indexed
        best_labels = best_labels - 1
        
        return best_labels, best_n, best_score


class MusicStructureAnalyzer:
    """
    Complete music structure analyzer implementing the paper's methodology.
    
    Pipeline:
    1. Extract audio features (spectrogram, chromagram)
    2. Generate self-similarity matrices
    3. Compute novelty scores
    4. Detect section boundaries
    5. Cluster similar sections
    6. Generate structure representation
    """
    
    def __init__(
        self,
        kernel_size: int = 64,
        novelty_threshold: float = 0.4,
        min_section_duration: float = 2.0,  # seconds
        ssm_resolution: int = 200,
    ):
        self.kernel_size = kernel_size
        self.novelty_threshold = novelty_threshold
        self.min_section_duration = min_section_duration
        self.ssm_resolution = ssm_resolution
        self.feature_extractor = audio_extractor
    
    def analyze(
        self, 
        audio_source: Any,
        audio_data: Optional[AudioData] = None
    ) -> Optional[StructuralAnalysis]:
        """
        Perform complete structural analysis on audio.
        
        Args:
            audio_source: Audio file path, BytesIO, or numpy array
            audio_data: Pre-computed AudioData (optional)
        
        Returns:
            StructuralAnalysis object with all results
        """
        if not SCIPY_AVAILABLE:
            logger.error("scipy required for structural analysis")
            return None
        
        try:
            # Extract features if not provided
            if audio_data is None:
                audio_data = self.feature_extractor.extract_all_features(
                    audio_source, compute_expensive=False
                )
            
            if audio_data is None:
                logger.error("Failed to extract audio features")
                return None
            
            # Initialize analysis result
            analysis = StructuralAnalysis(
                duration=audio_data.duration,
                n_frames=audio_data.chromagram.shape[1] if audio_data.chromagram is not None else 0,
                hop_length=audio_data.hop_length,
                sample_rate=audio_data.sample_rate,
            )
            
            # Step 1: Generate SSMs
            logger.info("Computing self-similarity matrices...")
            self._compute_ssm(audio_data, analysis)
            
            # Step 2: Compute novelty scores
            logger.info("Computing novelty scores...")
            self._compute_novelty(analysis)
            
            # Step 3: Detect boundaries
            logger.info("Detecting section boundaries...")
            self._detect_boundaries(audio_data, analysis)
            
            # Step 4: Extract section features and cluster
            logger.info("Clustering sections...")
            self._cluster_sections(audio_data, analysis)
            
            # Step 5: Create section objects
            logger.info("Creating section representations...")
            self._create_sections(audio_data, analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in structural analysis: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _compute_ssm(self, audio_data: AudioData, analysis: StructuralAnalysis):
        """Compute self-similarity matrices."""
        # SSM from spectrogram (for instrumental/energy changes)
        if audio_data.mel_spectrogram_db is not None:
            analysis.ssm_spectrogram = SelfSimilarityMatrix.compute(
                audio_data.mel_spectrogram_db,
                metric="cosine"
            )
        
        # SSM from chromagram (for harmonic changes)
        if audio_data.chromagram is not None:
            analysis.ssm_chromagram = SelfSimilarityMatrix.compute(
                audio_data.chromagram,
                metric="cosine"
            )
        
        # Combined SSM (weighted average)
        ssm_list = []
        weights = []
        
        if analysis.ssm_spectrogram is not None:
            ssm_list.append(analysis.ssm_spectrogram)
            weights.append(0.6)  # Spectrogram more important for boundaries
        
        if analysis.ssm_chromagram is not None:
            ssm_list.append(analysis.ssm_chromagram)
            weights.append(0.4)  # Chromagram for harmonic similarity
        
        if ssm_list:
            analysis.ssm_combined = SelfSimilarityMatrix.combine_ssm(ssm_list, weights)
            
            # Reduced resolution for visualization
            analysis.ssm_reduced = SelfSimilarityMatrix.reduce_resolution(
                analysis.ssm_combined,
                target_size=self.ssm_resolution
            )
    
    def _compute_novelty(self, analysis: StructuralAnalysis):
        """Compute novelty scores from SSMs."""
        # Novelty from spectrogram SSM (main source for boundaries)
        if analysis.ssm_spectrogram is not None:
            analysis.novelty_spectrogram = NoveltyDetector.compute_novelty(
                analysis.ssm_spectrogram,
                kernel_size=self.kernel_size
            )
        
        # Novelty from chromagram SSM
        if analysis.ssm_chromagram is not None:
            analysis.novelty_chromagram = NoveltyDetector.compute_novelty(
                analysis.ssm_chromagram,
                kernel_size=self.kernel_size
            )
        
        # Combined novelty
        if analysis.ssm_combined is not None:
            analysis.novelty_combined = NoveltyDetector.compute_novelty(
                analysis.ssm_combined,
                kernel_size=self.kernel_size
            )
    
    def _detect_boundaries(self, audio_data: AudioData, analysis: StructuralAnalysis):
        """Detect section boundaries from novelty curves."""
        # Use spectrogram novelty as primary (better for boundary detection)
        novelty = analysis.novelty_spectrogram
        if novelty is None:
            novelty = analysis.novelty_combined
        if novelty is None:
            novelty = analysis.novelty_chromagram
        
        if novelty is None:
            logger.warning("No novelty curve available for boundary detection")
            return
        
        # Calculate minimum distance in frames
        frames_per_second = audio_data.sample_rate / audio_data.hop_length
        min_distance = int(self.min_section_duration * frames_per_second)
        
        # Find boundaries
        analysis.boundary_frames = NoveltyDetector.find_boundaries(
            novelty,
            threshold=self.novelty_threshold,
            min_distance=min_distance
        )
        
        # Convert to times
        if audio_data.frame_times is not None and len(analysis.boundary_frames) > 0:
            max_idx = len(audio_data.frame_times) - 1
            valid_frames = analysis.boundary_frames[analysis.boundary_frames <= max_idx]
            analysis.boundary_times = audio_data.frame_times[valid_frames]
    
    def _cluster_sections(self, audio_data: AudioData, analysis: StructuralAnalysis):
        """Extract section features and perform clustering."""
        if analysis.boundary_frames is None or len(analysis.boundary_frames) < 2:
            logger.warning("Not enough boundaries for clustering")
            return
        
        # Extract features for each section
        chromagram = audio_data.chromagram
        spectrogram = audio_data.mel_spectrogram_db
        
        if chromagram is None or spectrogram is None:
            logger.warning("Missing features for clustering")
            return
        
        analysis.section_features = SectionClusterer.extract_section_features(
            chromagram,
            spectrogram,
            analysis.boundary_frames
        )
        
        # Perform clustering
        if analysis.section_features.shape[0] >= 3:
            labels, n_clusters, score = SectionClusterer.cluster_sections(
                analysis.section_features
            )
            analysis.cluster_labels = labels
            analysis.n_clusters = n_clusters
            analysis.silhouette_score = score
    
    def _create_sections(self, audio_data: AudioData, analysis: StructuralAnalysis):
        """Create Section objects from analysis results."""
        if analysis.boundary_frames is None or len(analysis.boundary_frames) < 2:
            return
        
        n_sections = len(analysis.boundary_frames) - 1
        
        # Section labels based on cluster
        section_labels = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
        
        for i in range(n_sections):
            start_frame = analysis.boundary_frames[i]
            end_frame = analysis.boundary_frames[i + 1]
            
            # Get times
            if audio_data.frame_times is not None:
                max_idx = len(audio_data.frame_times) - 1
                start_time = audio_data.frame_times[min(start_frame, max_idx)]
                end_time = audio_data.frame_times[min(end_frame, max_idx)]
            else:
                frames_per_second = audio_data.sample_rate / audio_data.hop_length
                start_time = start_frame / frames_per_second
                end_time = end_frame / frames_per_second
            
            # Get cluster ID and label
            cluster_id = -1
            label = f"Section {i + 1}"
            
            if analysis.cluster_labels is not None and i < len(analysis.cluster_labels):
                cluster_id = int(analysis.cluster_labels[i])
                if cluster_id < len(section_labels):
                    label = section_labels[cluster_id]
            
            # Get loudness for this section
            loudness = 0.0
            if audio_data.rms_energy is not None:
                section_energy = audio_data.rms_energy[start_frame:end_frame]
                if len(section_energy) > 0:
                    loudness = float(np.mean(section_energy))
            
            # Get features
            features = None
            if analysis.section_features is not None and i < len(analysis.section_features):
                features = analysis.section_features[i]
            
            section = Section(
                start_time=float(start_time),
                end_time=float(end_time),
                start_frame=int(start_frame),
                end_frame=int(end_frame),
                cluster_id=cluster_id,
                label=label,
                features=features,
                loudness=loudness,
            )
            
            analysis.sections.append(section)
    
    def compute_structural_similarity(
        self,
        analysis1: StructuralAnalysis,
        analysis2: StructuralAnalysis
    ) -> float:
        """
        Compute structural similarity between two songs.
        
        Compares:
        - Number and distribution of sections
        - Section patterns (e.g., ABABCB vs AABA)
        - Harmonic content of sections
        
        Returns:
            Similarity score (0-1)
        """
        if not analysis1.sections or not analysis2.sections:
            return 0.0
        
        # Compare number of sections
        n1 = len(analysis1.sections)
        n2 = len(analysis2.sections)
        section_count_sim = 1.0 - abs(n1 - n2) / max(n1, n2)
        
        # Compare section patterns
        pattern1 = [s.cluster_id for s in analysis1.sections]
        pattern2 = [s.cluster_id for s in analysis2.sections]
        pattern_sim = self._compare_patterns(pattern1, pattern2)
        
        # Compare section features
        feature_sim = 0.0
        if analysis1.section_features is not None and analysis2.section_features is not None:
            feature_sim = self._compare_section_features(
                analysis1.section_features,
                analysis2.section_features
            )
        
        # Weighted combination
        similarity = (
            0.2 * section_count_sim +
            0.4 * pattern_sim +
            0.4 * feature_sim
        )
        
        return float(max(0, min(1, similarity)))
    
    def _compare_patterns(self, pattern1: List[int], pattern2: List[int]) -> float:
        """Compare section patterns using edit distance."""
        # Normalize patterns to start from 0
        def normalize_pattern(p):
            mapping = {}
            result = []
            next_id = 0
            for x in p:
                if x not in mapping:
                    mapping[x] = next_id
                    next_id += 1
                result.append(mapping[x])
            return result
        
        p1 = normalize_pattern(pattern1)
        p2 = normalize_pattern(pattern2)
        
        # Compute edit distance
        m, n = len(p1), len(p2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if p1[i - 1] == p2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
        
        max_len = max(m, n)
        if max_len == 0:
            return 1.0
        
        return 1.0 - dp[m][n] / max_len
    
    def _compare_section_features(
        self,
        features1: np.ndarray,
        features2: np.ndarray
    ) -> float:
        """Compare section features using average similarity."""
        # Compute mean features for each song
        mean1 = np.mean(features1, axis=0)
        mean2 = np.mean(features2, axis=0)
        
        # Cosine similarity
        norm1 = np.linalg.norm(mean1)
        norm2 = np.linalg.norm(mean2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(mean1, mean2) / (norm1 * norm2))


# Global instance
music_structure_analyzer = MusicStructureAnalyzer()
