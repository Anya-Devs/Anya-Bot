import express from 'express';
import cors from 'cors';
import gelbooruRouter from './api/gelbooru';
import danbooruRouter from './api/danbooru';
import konachanRouter from './api/konachan';
import yandeRouter from './api/yande';
import jikanRouter from './api/jikan';
import botStatsRouter from './api/bot-stats';
import predictRouter from './api/predict';

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// API Routes
app.use('/api/gelbooru', gelbooruRouter);
app.use('/api/danbooru', danbooruRouter);
app.use('/api/konachan', konachanRouter);
app.use('/api/yande', yandeRouter);
app.use('/api/jikan', jikanRouter);
app.use('/api/bot-stats', botStatsRouter);
app.use('/api', predictRouter);

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok' });
});

// Start server
app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});

export default app;
