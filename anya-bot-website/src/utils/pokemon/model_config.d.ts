// Type declarations for model_config.js
export const ONNX_PATH: string;
export const LABELS_PATH: string;

// Sample Poketwo spawn image URL for testing predictions
export const SAMPLE_SPAWN_IMAGE_URL: string;

export interface ModelConfig {
  inputShape: number[];
  inputSize: number;
  inputName: string;
  outputName: string;
  normalization: {
    mean: number[];
    std: number[];
  };
}

export const MODEL_CONFIG: ModelConfig;

export const POKEMON_TYPES: Record<string, string>;
