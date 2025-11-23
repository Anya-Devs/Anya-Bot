// @ts-ignore
import * as ort from 'onnxruntime-node';
import express from 'express';
import path from 'path';
import fs from 'fs';
import sharp from 'sharp';

const router = express.Router();

// ONNX model path
const ONNX_PATH = path.join(process.cwd(), 'public', 'models', 'pokemon', 'pokemon_cnn_v2.onnx');
const LABELS_PATH = path.join(process.cwd(), 'public', 'models', 'pokemon', 'labels_v2.json');

let model: ort.InferenceSession | null = null;
let labels: string[] = [];

// Load model and labels
const loadModel = async () => {
  if (model) return;
  try {
    model = await ort.InferenceSession.create(ONNX_PATH);
    const labelsData = fs.readFileSync(LABELS_PATH, 'utf8');
    const labelsObj = JSON.parse(labelsData);
    labels = Object.keys(labelsObj).sort((a, b) => Number(a) - Number(b)).map(key => labelsObj[key].toLowerCase());
    console.log('Prediction model loaded');
  } catch (error) {
    console.error('Failed to load prediction model:', error);
  }
};

// Preprocess image
const preprocessImage = async (imageBuffer: Buffer) => {
  const size = 224; // Assuming 224x224 input
  const resizedBuffer = await sharp(imageBuffer)
    .resize(size, size, { fit: 'fill' })
    .raw()
    .toBuffer();

  const input = new Float32Array(size * size * 3);
  for (let i = 0; i < resizedBuffer.length; i += 3) {
    input[i / 3 * 3] = resizedBuffer[i] / 255.0;     // R
    input[i / 3 * 3 + 1] = resizedBuffer[i + 1] / 255.0; // G
    input[i / 3 * 3 + 2] = resizedBuffer[i + 2] / 255.0; // B
  }
  return input;
};

// Predict endpoint
router.post('/predict', async (req, res) => {
  try {
    await loadModel();
    if (!model || labels.length === 0) {
      return res.status(500).json({ error: 'Model not loaded' });
    }

    const { image_url } = req.body;
    if (!image_url) {
      return res.status(400).json({ error: 'image_url required' });
    }

    // Fetch image
    const imageResponse = await fetch(image_url);
    const imageBuffer = Buffer.from(await imageResponse.arrayBuffer());

    const input = await preprocessImage(imageBuffer);
    const tensor = new ort.Tensor('float32', input, [1, 3, 224, 224]);

    const feeds = { input: tensor };
    const results = await model.run(feeds);
    const output = results.output.data;

    let maxIndex = 0;
    let maxProb = output[0];
    for (let i = 1; i < output.length; i++) {
      if (output[i] > maxProb) {
        maxProb = output[i];
        maxIndex = i;
      }
    }

    const prediction = {
      name: labels[maxIndex],
      confidence: maxProb
    };

    const response = {
      model: 'pokemon_cnn_v2',
      labels: labels,
      image_url: image_url,
      result: [prediction]
    };

    res.json(response);
  } catch (error) {
    console.error('Prediction error:', error);
    res.status(500).json({ error: 'Prediction failed' });
  }
});

export default router;
