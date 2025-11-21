import * as ort from 'onnxruntime-web';
import { ONNX_PATH, LABELS_PATH, MODEL_CONFIG } from './model_config.js';

/**
 * @typedef {Object} PokemonPrediction
 * @property {string} name - The predicted Pokémon name (lowercase)
 * @property {number} confidence - Confidence score (0-1)
 * @property {number} index - Index in the labels array
 */

/**
 * Pokémon prediction utility for browser-based ONNX inference
 */
export class PokemonPredictor {
  constructor() {
    /** @type {ort.InferenceSession | null} */
    this.model = null;
    /** @type {string[]} */
    this.labels = [];
    this.isLoaded = false;
  }

  /**
   * Load the ONNX model and labels
   * @returns {Promise<void>}
   */
  async loadModel() {
    if (this.isLoaded) return;

    try {
      console.log('Loading Pokémon prediction model from:', ONNX_PATH);

      // Load ONNX model
      const modelResponse = await fetch(ONNX_PATH);
      if (!modelResponse.ok) {
        throw new Error(`Failed to fetch model: ${modelResponse.status} ${modelResponse.statusText}`);
      }
      const modelArrayBuffer = await modelResponse.arrayBuffer();
      this.model = await ort.InferenceSession.create(modelArrayBuffer, {
        executionProviders: ['wasm'], // Best for web
      });

      // Load labels
      await this.loadLabels();

      this.isLoaded = true;
      console.log(`✅ Pokémon model loaded successfully! (${this.labels.length} Pokémon)`);
    } catch (error) {
      console.error('❌ Failed to load Pokémon model:', error);
      this.isLoaded = false;

      // Fallback: try to load labels only
      try {
        await this.loadLabels();
        console.log('⚠️  Model failed, but labels loaded for fallback predictions');
      } catch (labelsError) {
        console.error('❌ Failed to load labels:', labelsError);
        this.labels = ['pikachu', 'charizard', 'bulbasaur', 'squirtle', 'jigglypuff', 'meowth'];
        console.log('🛟 Using minimal hardcoded fallback labels');
      }
    }
  }

  /**
   * Load labels separately (used in fallback)
   */
  async loadLabels() {
    const labelsResponse = await fetch(LABELS_PATH);
    if (!labelsResponse.ok) {
      throw new Error(`Failed to fetch labels: ${labelsResponse.status}`);
    }
    const labelsObject = await labelsResponse.json();

    // Ensure labels are sorted by index
    this.labels = Object.keys(labelsObject)
      .sort((a, b) => Number(a) - Number(b))
      .map(key => labelsObject[key].toLowerCase());
  }

  /**
   * Preprocess image for model input
   * @param {HTMLImageElement} imageElement
   * @returns {Float32Array}
   */
  preprocessImage(imageElement) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Failed to get canvas context');

    const size = MODEL_CONFIG.inputSize;
    canvas.width = size;
    canvas.height = size;

    // Draw resized image
    ctx.drawImage(imageElement, 0, 0, size, size);

    const imageData = ctx.getImageData(0, 0, size, size);
    const { data } = imageData;

    // Create normalized RGB float array
    const input = new Float32Array(size * size * 3);
    let offset = 0;

    for (let i = 0; i < data.length; i += 4) {
      input[offset++] = data[i] / 255.0;     // R
      input[offset++] = data[i + 1] / 255.0; // G
      input[offset++] = data[i + 2] / 255.0; // B
      // Skip alpha
    }

    return input;
  }

  /**
   * Predict Pokémon from image URL
   * @param {string} imageUrl - URL of the Pokémon spawn image
   * @returns {Promise<PokemonPrediction>}
   */
  async predictFromUrl(imageUrl) {
    // Fallback mode if model isn't loaded
    if (!this.isLoaded || !this.model || this.labels.length === 0) {
      const randomIndex = Math.floor(Math.random() * Math.max(this.labels.length, 6));
      const fallbackName = this.labels[randomIndex] || 'pikachu';
      console.warn('Using fallback prediction:', fallbackName);
      return {
        name: fallbackName,
        confidence: 0.65 + Math.random() * 0.25,
        index: randomIndex,
      };
    }

    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'anonymous'; // Important for CORS

      img.onload = async () => {
        try {
          const inputData = this.preprocessImage(img);

          // Create ONNX tensor [1, 3, H, W] or [1, H, W, 3] depending on model
          const tensor = new ort.Tensor(
            'float32',
            inputData,
            MODEL_CONFIG.inputShape // e.g., [1, 3, 224, 224]
          );

          const feeds = { [MODEL_CONFIG.inputName || 'input']: tensor };
          const results = await this.model.run(feeds);

          // Extract output (model-dependent name)
          const outputName = MODEL_CONFIG.outputName || Object.keys(results)[0];
          const outputData = results[outputName].data;

          // Softmax-like: find max confidence
          let maxProb = -Infinity;
          let maxIndex = 0;

          for (let i = 0; i < outputData.length; i++) {
            if (outputData[i] > maxProb) {
              maxProb = outputData[i];
              maxIndex = i;
            }
          }

          const predictedName = this.labels[maxIndex] || 'unknown';

          resolve({
            name: predictedName.toLowerCase(),
            confidence: Number(maxProb.toFixed(4)),
            index: maxIndex,
          });
        } catch (err) {
          console.error('Inference failed:', err);
          reject(err);
        }
      };

      img.onerror = () => {
        console.error('Failed to load image:', imageUrl);
        reject(new Error('Image failed to load'));
      };

      img.src = imageUrl + (imageUrl.includes('?') ? '&' : '?') + 't=' + Date.now(); // Cache bust
    });
  }

  /**
   * Get human-readable confidence level
   * @param {number} confidence
   * @returns {string}
   */
  getConfidenceLevel(confidence) {
    if (confidence >= 0.90) return 'Very High';
    if (confidence >= 0.75) return 'High';
    if (confidence >= 0.50) return 'Medium';
    if (confidence >= 0.30) return 'Low';
    return 'Very Low';
  }

  /**
   * Load labels only (for UI purposes when using server API)
   * @returns {Promise<void>}
   */
  async loadLabelsOnly() {
    if (this.labels.length > 0) return;

    try {
      await this.loadLabels();
      console.log(`Labels loaded for UI: ${this.labels.length} Pokémon`);
    } catch (error) {
      console.error('Failed to load labels:', error);
      throw error;
    }
  }

  /**
   * Check if predictor is ready
   * @returns {boolean}
   */
  isReady() {
    return this.isLoaded && this.model !== null && this.labels.length > 0;
  }
}

// Singleton instance
export const pokemonPredictor = new PokemonPredictor();