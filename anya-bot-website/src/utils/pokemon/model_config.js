// Pokémon spawn prediction model configuration
export const ONNX_PATH = "/models/pokemon/pokemon_cnn_v2.onnx";
export const LABELS_PATH = "/models/pokemon/labels_v2.json";

// Sample Poketwo spawn image URL for testing predictions
export const SAMPLE_SPAWN_IMAGE_URL = "/poketwo-spawn.png";

// WebAssembly configuration - using CDN for better reliability
export const WASM_PATH = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.15.1/dist/ort-wasm-simd-threaded.wasm';
export const WORKER_PATH = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.15.1/dist/ort-wasm-simd-threaded.worker.js';

// Model configuration constants
export const MODEL_CONFIG = {
  inputShape: [1, 3, 224, 224], // Batch size, channels, height, width
  inputSize: 224, // Image size for preprocessing
  inputName: 'input', // ONNX model input name
  outputName: 'output', // ONNX model output name
  normalization: {
    mean: [0.485, 0.456, 0.406], // ImageNet means
    std: [0.229, 0.224, 0.225]   // ImageNet stds
  }
};

// Pokémon type colors for UI (optional)
export const POKEMON_TYPES = {
  normal: '#A8A878',
  fire: '#F08030',
  water: '#6890F0',
  electric: '#F8D030',
  grass: '#78C850',
  ice: '#98D8D8',
  fighting: '#C03028',
  poison: '#A040A0',
  ground: '#E0C068',
  flying: '#A890F0',
  psychic: '#F85888',
  bug: '#A8B820',
  rock: '#B8A038',
  ghost: '#705898',
  dragon: '#7038F8',
  dark: '#705848',
  steel: '#B8B8D0',
  fairy: '#EE99AC'
};
