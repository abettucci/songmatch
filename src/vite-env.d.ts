/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_STEM_ARTIFACTS_HOST?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
