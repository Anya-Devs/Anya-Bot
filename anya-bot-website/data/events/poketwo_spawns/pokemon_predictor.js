import * as ort from 'onnxruntime-web';
import { ONNX_PATH, LABELS_PATH, MODEL_CONFIG } from './model_config.js';

/**
 * Pokémon prediction utility for browser-based ONNX inference
 */
export class PokemonPredictor {
  constructor() {
    this.model = null;
    this.labels = [];
    this.isLoaded = false;
  }

  /**
   * Load the ONNX model and labels
   */
  async loadModel() {
    try {
      console.log('Loading Pokémon prediction model...');

      // Load ONNX model
      const modelResponse = await fetch(ONNX_PATH);
      const modelArrayBuffer = await modelResponse.arrayBuffer();
      this.model = await ort.InferenceSession.create(modelArrayBuffer);

      // Load labels
      const labelsResponse = await fetch(LABELS_PATH);
      this.labels = await labelsResponse.json();

      this.isLoaded = true;
      console.log('Pokémon model loaded successfully');
      console.log(`Loaded ${this.labels.length} Pokémon labels`);

    } catch (error) {
      console.error('Failed to load Pokémon model:', error);
      throw error;
    }
  }

  /**
   * Preprocess image for model input
   */
  preprocessImage(imageElement) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    // Set canvas size to model input size
    canvas.width = MODEL_CONFIG.inputSize;
    canvas.height = MODEL_CONFIG.inputSize;

    // Draw and resize image
    ctx.drawImage(imageElement, 0, 0, MODEL_CONFIG.inputSize, MODEL_CONFIG.inputSize);

    // Get image data
    const imageData = ctx.getImageData(0, 0, MODEL_CONFIG.inputSize, MODEL_CONFIG.inputSize);
    const { data } = imageData;

    // Convert to RGB and normalize (0-1 range)
    const input = new Float32Array(MODEL_CONFIG.inputSize * MODEL_CONFIG.inputSize * 3);

    for (let i = 0; i < MODEL_CONFIG.inputSize * MODEL_CONFIG.inputSize; i++) {
      const pixelIndex = i * 4;
      // RGB channels (skip alpha)
      input[i * 3] = data[pixelIndex] / 255.0;         // R
      input[i * 3 + 1] = data[pixelIndex + 1] / 255.0; // G
      input[i * 3 + 2] = data[pixelIndex + 2] / 255.0; // B
    }

    return input;
  }

  /**
   * Predict Pokémon from image URL
   */
  async predictFromUrl(imageUrl) {
    if (!this.isLoaded || !this.model) {
      throw new Error('Model not loaded. Call loadModel() first.');
    }

    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';

      img.onload = async () => {
        try {
          // Preprocess image
          const input = this.preprocessImage(img);

          // Create tensor
          const tensor = new ort.Tensor('float32', input, MODEL_CONFIG.inputShape);

          // Run inference
          const feeds = { input: tensor };
          const results = await this.model.run(feeds);

          // Get prediction
          const output = results.output.data;
          const predictions = Array.from(output);

          // Find highest probability
          let maxIndex = 0;
          let maxProb = predictions[0];

          for (let i = 1; i < predictions.length; i++) {
            if (predictions[i] > maxProb) {
              maxProb = predictions[i];
              maxIndex = i;
            }
          }

          const predictedName = this.labels[maxIndex] || 'unknown';
          const confidence = maxProb;

          resolve({
            name: predictedName.toLowerCase(),
            confidence: confidence,
            index: maxIndex
          });

        } catch (error) {
          reject(error);
        }
      };

      img.onerror = () => reject(new Error('Failed to load image'));
      img.src = imageUrl;
    });
  }

  /**
   * Get prediction confidence as percentage
   */
  getConfidenceLevel(confidence) {
    if (confidence > 0.8) return 'Very High';
    if (confidence > 0.6) return 'High';
    if (confidence > 0.4) return 'Medium';
    if (confidence > 0.2) return 'Low';
    return 'Very Low';
  }

  /**
   * Check if model is ready for predictions
   */
  isReady() {
    return this.isLoaded && this.model !== null && this.labels.length > 0;
  }
}

// Export singleton instance
export const pokemonPredictor = new PokemonPredictor();
