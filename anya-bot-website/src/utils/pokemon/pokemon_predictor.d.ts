// Type declarations for pokemon_predictor.js
export interface PokemonPrediction {
  name: string;
  confidence: number;
  index: number;
}

export class PokemonPredictor {
  model: any;
  labels: string[];
  isLoaded: boolean;

  constructor();
  loadModel(modelPath?: string): Promise<void>;
  predictFromUrl(imageUrl: string): Promise<PokemonPrediction>;
  getConfidenceLevel(confidence: number): string;
  isReady(): boolean;
}

export const pokemonPredictor: PokemonPredictor;
