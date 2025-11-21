// Pokémon spawn prediction model configuration
export const ONNX_PATH = "/models/pokemon/pokemon_cnn_v2.onnx";
export const LABELS_PATH = "/models/pokemon/labels_v2.json";

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
