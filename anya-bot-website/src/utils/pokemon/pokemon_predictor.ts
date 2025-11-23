import * as ort from 'onnxruntime-web';
import { ONNX_PATH, LABELS_PATH, MODEL_CONFIG } from './model_config.js';

export interface PokemonPrediction {
  name: string;
  confidence: number;
  index: number;
  error?: string;
}

/**
 * Pokémon prediction utility for browser-based ONNX inference
 */
export class PokemonPredictor {
  private model: ort.InferenceSession | null = null;
  private labels: string[] = [];
  private isLoaded: boolean = false;
  private error: string | null = null;

  /**
   * Get the current error state
   */
  public getError(): string | null {
    return this.error;
  }

  /**
   * Clear any current error
   */
  public clearError(): void {
    this.error = null;
  }

  /**
   * Load the ONNX model and labels
   * @param modelPath Optional custom path to the model file
   */
  async loadModel(modelPath?: string): Promise<void> {
    if (this.isLoaded) return;
    this.clearError();

    const modelUrl = modelPath || ONNX_PATH;

    try {
      console.log('Loading Pokémon prediction model from:', modelUrl);

      // Load ONNX model
      const modelResponse = await fetch(modelUrl);
      if (!modelResponse.ok) {
        throw new Error(`Failed to fetch model: ${modelResponse.status} ${modelResponse.statusText}`);
      }
      const modelArrayBuffer = await modelResponse.arrayBuffer();
      this.model = await ort.InferenceSession.create(modelArrayBuffer, {
        executionProviders: ['webgpu', 'wasm'], // WebGPU first, fallback to WASM
      });

      // Load labels
      await this.loadLabels();

      this.isLoaded = true;
      console.log(`✅ Pokémon model loaded successfully! (${this.labels.length} Pokémon)`);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error loading model';
      console.error('❌ Failed to load Pokémon model:', error);
      this.error = `Failed to load prediction model: ${errorMsg}`;
      this.isLoaded = false;

      // Fallback: try to load labels only
      try {
        await this.loadLabels();
        console.log('⚠️  Model failed, but labels loaded for fallback predictions');
      } catch (labelsError) {
        const labelsErrorMsg = labelsError instanceof Error ? labelsError.message : 'Unknown error loading labels';
        console.error('❌ Failed to load labels:', labelsError);
        this.labels = ['pikachu', 'charizard', 'bulbasaur', 'squirtle', 'jigglypuff', 'meowth'];
        this.error = `Using fallback mode: ${labelsErrorMsg}`;
        console.log('🛟 Using minimal hardcoded fallback labels');
      }
    }
  }

  /**
   * Load labels from JSON file
   */
  private async loadLabels(): Promise<void> {
    const labelsResponse = await fetch(LABELS_PATH);
    if (!labelsResponse.ok) {
      throw new Error(`Failed to fetch labels: ${labelsResponse.status}`);
    }
    const labelsObject: Record<string, string> = await labelsResponse.json();

    // Ensure labels are sorted by index
    this.labels = Object.keys(labelsObject)
      .sort((a, b) => Number(a) - Number(b))
      .map(key => labelsObject[key].toLowerCase());
  }

  /**
   * Preprocess image for model input
   */
  private preprocessImage(imageElement: HTMLImageElement): Float32Array {
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
   */
  async predictFromUrl(imageUrl: string): Promise<PokemonPrediction> {
    this.clearError();
    
    // Fallback mode if model isn't loaded
    if (!this.isLoaded || !this.model || this.labels.length === 0) {
      const randomIndex = Math.floor(Math.random() * Math.max(this.labels.length, 6));
      const fallbackName = this.labels[randomIndex] || 'pikachu';
      const errorMsg = 'Model not loaded, using fallback prediction';
      console.warn(errorMsg, fallbackName);
      this.error = errorMsg;
      
      return {
        name: fallbackName,
        confidence: 0.65 + Math.random() * 0.25,
        index: randomIndex,
        error: errorMsg
      };
    }

    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';

      img.onload = async () => {
        try {
          const inputData = this.preprocessImage(img);
          const tensor = new ort.Tensor(
            'float32',
            inputData,
            MODEL_CONFIG.inputShape
          );

          const feeds = { [MODEL_CONFIG.inputName || 'input']: tensor };
          const results = await this.model!.run(feeds);

          // Extract output (model-dependent name)
          const outputName = MODEL_CONFIG.outputName || Object.keys(results)[0];
          const outputData = results[outputName].data as Float32Array;

          // Find max confidence
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
          const errorMsg = err instanceof Error ? err.message : 'Prediction failed';
          console.error('Inference failed:', errorMsg);
          this.error = `Prediction failed: ${errorMsg}`;
          reject(new Error(errorMsg));
        }
      };

      img.onerror = () => {
        const errorMsg = `Failed to load image: ${imageUrl}`;
        console.error(errorMsg);
        this.error = errorMsg;
        reject(new Error(errorMsg));
      };

      img.src = imageUrl + (imageUrl.includes('?') ? '&' : '?') + 't=' + Date.now(); // Cache bust
    });
  }

  /**
   * Get human-readable confidence level
   */
  getConfidenceLevel(confidence: number): string {
    if (confidence >= 0.90) return 'Very High';
    if (confidence >= 0.75) return 'High';
    if (confidence >= 0.50) return 'Medium';
    if (confidence >= 0.30) return 'Low';
    return 'Very Low';
  }

  /**
   * Check if predictor is ready
   */
  isReady(): boolean {
    return this.isLoaded && this.labels.length > 0;
  }
}

// Singleton instance
export const pokemonPredictor = new PokemonPredictor();
