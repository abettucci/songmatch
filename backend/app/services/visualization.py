"""
Visualization Module for Structural Analysis.

Generates visual representations of:
- Self-Similarity Matrices (SSM)
- Novelty curves
- Section boundaries
- Structure diagrams

These visualizations help understand and validate the structural analysis results.
"""

import numpy as np
from typing import Optional, List, Dict, Any, Tuple
import logging
import io
import base64

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.colors import LinearSegmentedColormap
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available for visualization")

from app.services.structural_analysis import StructuralAnalysis, Section


class StructureVisualizer:
    """
    Generates visualizations for music structure analysis.
    
    All methods return base64-encoded PNG images that can be
    embedded directly in web responses.
    """
    
    # Color scheme for sections
    SECTION_COLORS = [
        '#FF6B6B',  # A - Red
        '#4ECDC4',  # B - Teal
        '#45B7D1',  # C - Blue
        '#96CEB4',  # D - Green
        '#FFEAA7',  # E - Yellow
        '#DDA0DD',  # F - Plum
        '#98D8C8',  # G - Mint
        '#F7DC6F',  # H - Gold
        '#BB8FCE',  # I - Purple
        '#85C1E9',  # J - Light Blue
    ]
    
    @staticmethod
    def _fig_to_base64(fig: Any) -> str:
        """Convert matplotlib figure to base64 string."""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return img_str
    
    @classmethod
    def plot_ssm(
        cls,
        ssm: np.ndarray,
        title: str = "Self-Similarity Matrix",
        boundaries: Optional[np.ndarray] = None,
        frame_times: Optional[np.ndarray] = None,
        figsize: Tuple[int, int] = (10, 10),
    ) -> Optional[str]:
        """
        Plot Self-Similarity Matrix with optional section boundaries.
        
        Args:
            ssm: Self-similarity matrix
            title: Plot title
            boundaries: Optional boundary frame indices
            frame_times: Optional frame time array for axis labels
            figsize: Figure size
        
        Returns:
            Base64-encoded PNG image
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available for SSM plot")
            return None
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # Create custom colormap (dark blue to white to dark red)
        colors = ['#2C3E50', '#3498DB', '#ECF0F1', '#E74C3C', '#C0392B']
        cmap = LinearSegmentedColormap.from_list('ssm', colors)
        
        # Plot SSM
        im = ax.imshow(ssm, cmap=cmap, aspect='equal', origin='lower')
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Similarity', rotation=270, labelpad=15)
        
        # Add boundary lines
        if boundaries is not None:
            for b in boundaries:
                ax.axhline(y=b, color='white', linewidth=0.5, alpha=0.7)
                ax.axvline(x=b, color='white', linewidth=0.5, alpha=0.7)
        
        # Labels
        ax.set_xlabel('Time (frames)')
        ax.set_ylabel('Time (frames)')
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        # Add time labels if available
        if frame_times is not None and len(frame_times) > 0:
            n_ticks = 5
            tick_positions = np.linspace(0, len(frame_times) - 1, n_ticks, dtype=int)
            tick_labels = [f"{frame_times[i]:.1f}s" for i in tick_positions]
            ax.set_xticks(tick_positions)
            ax.set_xticklabels(tick_labels)
            ax.set_yticks(tick_positions)
            ax.set_yticklabels(tick_labels)
        
        return cls._fig_to_base64(fig)
    
    @classmethod
    def plot_novelty(
        cls,
        novelty: np.ndarray,
        boundaries: Optional[np.ndarray] = None,
        frame_times: Optional[np.ndarray] = None,
        title: str = "Novelty Score",
        figsize: Tuple[int, int] = (12, 4),
    ) -> Optional[str]:
        """
        Plot novelty curve with detected boundaries.
        
        Args:
            novelty: Novelty score array
            boundaries: Detected boundary frames
            frame_times: Frame time array
            title: Plot title
            figsize: Figure size
        
        Returns:
            Base64-encoded PNG image
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available for novelty plot")
            return None
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # X-axis
        if frame_times is not None and len(frame_times) == len(novelty):
            x = frame_times
            xlabel = 'Time (seconds)'
        else:
            x = np.arange(len(novelty))
            xlabel = 'Frame'
        
        # Plot novelty curve
        ax.fill_between(x, novelty, alpha=0.3, color='#3498DB')
        ax.plot(x, novelty, color='#2980B9', linewidth=1.5)
        
        # Plot boundaries
        if boundaries is not None:
            for b in boundaries:
                if frame_times is not None and b < len(frame_times):
                    bx = frame_times[b]
                else:
                    bx = b
                ax.axvline(x=bx, color='#E74C3C', linewidth=2, linestyle='--', alpha=0.8)
        
        ax.set_xlabel(xlabel)
        ax.set_ylabel('Novelty Score')
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_ylim(0, max(novelty) * 1.1)
        ax.grid(True, alpha=0.3)
        
        return cls._fig_to_base64(fig)
    
    @classmethod
    def plot_structure(
        cls,
        sections: List[Section],
        duration: float,
        title: str = "Song Structure",
        figsize: Tuple[int, int] = (14, 3),
    ) -> Optional[str]:
        """
        Plot song structure as colored sections.
        
        Args:
            sections: List of Section objects
            duration: Total song duration
            title: Plot title
            figsize: Figure size
        
        Returns:
            Base64-encoded PNG image
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available for structure plot")
            return None
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot each section
        legend_patches = {}
        
        for section in sections:
            color_idx = section.cluster_id % len(cls.SECTION_COLORS)
            color = cls.SECTION_COLORS[color_idx]
            
            # Draw section rectangle
            rect = mpatches.Rectangle(
                (section.start_time, 0),
                section.duration,
                1,
                facecolor=color,
                edgecolor='white',
                linewidth=2,
            )
            ax.add_patch(rect)
            
            # Add label in center
            center_x = section.start_time + section.duration / 2
            ax.text(
                center_x, 0.5, section.label,
                ha='center', va='center',
                fontsize=14, fontweight='bold',
                color='white' if color_idx < 5 else 'black',
            )
            
            # Track for legend
            if section.label not in legend_patches:
                legend_patches[section.label] = mpatches.Patch(
                    color=color, label=section.label
                )
        
        # Configure axes
        ax.set_xlim(0, duration)
        ax.set_ylim(0, 1)
        ax.set_xlabel('Time (seconds)')
        ax.set_yticks([])
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        # Add legend
        if legend_patches:
            ax.legend(
                handles=list(legend_patches.values()),
                loc='upper right',
                ncol=len(legend_patches),
            )
        
        # Add time markers
        for t in range(0, int(duration) + 1, 30):
            ax.axvline(x=t, color='gray', linewidth=0.5, alpha=0.5)
        
        return cls._fig_to_base64(fig)
    
    @classmethod
    def plot_combined(
        cls,
        analysis: StructuralAnalysis,
        frame_times: Optional[np.ndarray] = None,
        figsize: Tuple[int, int] = (14, 12),
    ) -> Optional[str]:
        """
        Create combined visualization with SSM, novelty, and structure.
        
        Args:
            analysis: StructuralAnalysis object
            frame_times: Frame time array
            figsize: Figure size
        
        Returns:
            Base64-encoded PNG image
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available for combined plot")
            return None
        
        fig = plt.figure(figsize=figsize)
        
        # Create grid
        gs = fig.add_gridspec(3, 2, height_ratios=[2, 1, 0.5], hspace=0.3, wspace=0.3)
        
        # 1. SSM (left, top)
        ax_ssm = fig.add_subplot(gs[0, 0])
        if analysis.ssm_combined is not None:
            ssm = analysis.ssm_reduced if analysis.ssm_reduced is not None else analysis.ssm_combined
            colors = ['#2C3E50', '#3498DB', '#ECF0F1', '#E74C3C', '#C0392B']
            cmap = LinearSegmentedColormap.from_list('ssm', colors)
            im = ax_ssm.imshow(ssm, cmap=cmap, aspect='equal', origin='lower')
            plt.colorbar(im, ax=ax_ssm, fraction=0.046, pad=0.04)
            ax_ssm.set_title('Self-Similarity Matrix', fontweight='bold')
            ax_ssm.set_xlabel('Time')
            ax_ssm.set_ylabel('Time')
        
        # 2. Chromagram SSM (right, top)
        ax_chroma = fig.add_subplot(gs[0, 1])
        if analysis.ssm_chromagram is not None:
            ssm_chroma = analysis.ssm_chromagram
            if ssm_chroma.shape[0] > 200:
                from app.services.structural_analysis import SelfSimilarityMatrix
                ssm_chroma = SelfSimilarityMatrix.reduce_resolution(ssm_chroma, 200)
            im2 = ax_chroma.imshow(ssm_chroma, cmap='magma', aspect='equal', origin='lower')
            plt.colorbar(im2, ax=ax_chroma, fraction=0.046, pad=0.04)
            ax_chroma.set_title('Chromagram SSM (Harmonic)', fontweight='bold')
            ax_chroma.set_xlabel('Time')
            ax_chroma.set_ylabel('Time')
        
        # 3. Novelty curve (middle, full width)
        ax_novelty = fig.add_subplot(gs[1, :])
        novelty = analysis.novelty_combined
        if novelty is None:
            novelty = analysis.novelty_spectrogram
        
        if novelty is not None:
            x = np.arange(len(novelty))
            ax_novelty.fill_between(x, novelty, alpha=0.3, color='#3498DB')
            ax_novelty.plot(x, novelty, color='#2980B9', linewidth=1.5)
            
            if analysis.boundary_frames is not None:
                for b in analysis.boundary_frames:
                    ax_novelty.axvline(x=b, color='#E74C3C', linewidth=2, 
                                       linestyle='--', alpha=0.8)
            
            ax_novelty.set_title('Novelty Score (Section Boundaries)', fontweight='bold')
            ax_novelty.set_xlabel('Frame')
            ax_novelty.set_ylabel('Novelty')
            ax_novelty.grid(True, alpha=0.3)
        
        # 4. Structure (bottom, full width)
        ax_struct = fig.add_subplot(gs[2, :])
        if analysis.sections:
            legend_patches = {}
            for section in analysis.sections:
                color_idx = section.cluster_id % len(cls.SECTION_COLORS)
                color = cls.SECTION_COLORS[color_idx]
                
                rect = mpatches.Rectangle(
                    (section.start_time, 0), section.duration, 1,
                    facecolor=color, edgecolor='white', linewidth=2,
                )
                ax_struct.add_patch(rect)
                
                center_x = section.start_time + section.duration / 2
                ax_struct.text(
                    center_x, 0.5, section.label,
                    ha='center', va='center',
                    fontsize=12, fontweight='bold',
                    color='white' if color_idx < 5 else 'black',
                )
                
                if section.label not in legend_patches:
                    legend_patches[section.label] = mpatches.Patch(
                        color=color, label=section.label
                    )
            
            ax_struct.set_xlim(0, analysis.duration)
            ax_struct.set_ylim(0, 1)
            ax_struct.set_xlabel('Time (seconds)')
            ax_struct.set_yticks([])
            ax_struct.set_title(
                f'Structure: {cls._get_pattern(analysis.sections)}', 
                fontweight='bold'
            )
            
            if legend_patches:
                ax_struct.legend(
                    handles=list(legend_patches.values()),
                    loc='upper right', ncol=len(legend_patches),
                )
        
        fig.suptitle('Music Structure Analysis', fontsize=16, fontweight='bold', y=1.02)
        
        return cls._fig_to_base64(fig)
    
    @staticmethod
    def _get_pattern(sections: List[Section]) -> str:
        """Get structure pattern string from sections."""
        labels = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
        pattern = ""
        for section in sections:
            if section.cluster_id >= 0 and section.cluster_id < len(labels):
                pattern += labels[section.cluster_id]
        return pattern
    
    @classmethod
    def generate_all_visualizations(
        cls,
        analysis: StructuralAnalysis,
        frame_times: Optional[np.ndarray] = None,
    ) -> Dict[str, Optional[str]]:
        """
        Generate all available visualizations.
        
        Args:
            analysis: StructuralAnalysis object
            frame_times: Frame time array
        
        Returns:
            Dictionary with visualization names and base64 images
        """
        visualizations = {}
        
        # Combined view
        visualizations["combined"] = cls.plot_combined(analysis, frame_times)
        
        # Individual SSM
        if analysis.ssm_combined is not None:
            ssm = analysis.ssm_reduced if analysis.ssm_reduced is not None else analysis.ssm_combined
            visualizations["ssm"] = cls.plot_ssm(
                ssm, 
                "Self-Similarity Matrix",
                analysis.boundary_frames,
                frame_times,
            )
        
        # Novelty curve
        novelty = analysis.novelty_combined or analysis.novelty_spectrogram
        if novelty is not None:
            visualizations["novelty"] = cls.plot_novelty(
                novelty,
                analysis.boundary_frames,
                frame_times,
            )
        
        # Structure
        if analysis.sections:
            visualizations["structure"] = cls.plot_structure(
                analysis.sections,
                analysis.duration,
            )
        
        return visualizations


# Global instance
structure_visualizer = StructureVisualizer()
