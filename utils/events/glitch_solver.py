
from data.local.const import primary_color
import cv2, numpy as np, requests, io, itertools, discord, re
from collections import Counter

class ImgPuzzle:
    def __init__(self, bot):
        self.bot, self.orb, self.bf = bot, cv2.ORB_create(nfeatures=1000), cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    def load(self, url):
        img_data = io.BytesIO(requests.get(url).content)
        if img_data is None: raise ValueError("Failed to fetch image")
        return cv2.imdecode(np.frombuffer(img_data.read(), np.uint8), cv2.IMREAD_COLOR)

    def split(self, img):
        h, w = img.shape[:2]
        mx, my = w // 2, h // 2
        return [img[:my, :mx], img[:my, mx:], img[my:, :mx], img[my:, mx:]]

    def edge_similarity(self, p1, p2, d):
        e1, e2 = (p1[-5:, :], p2[:5, :]) if d == 'horizontal' else (p1[:, -5:], p2[:, :5])
        min_h, min_w = min(e1.shape[0], e2.shape[0]), min(e1.shape[1], e2.shape[1])
        e1, e2 = cv2.resize(e1, (min_w, min_h)), cv2.resize(e2, (min_w, min_h))
        return -np.sum(np.abs(e1.astype(float) - e2.astype(float)))

    def feature_similarity(self, p1, p2):
        g1, g2 = cv2.cvtColor(p1, cv2.COLOR_BGR2GRAY), cv2.cvtColor(p2, cv2.COLOR_BGR2GRAY)
        kp1, des1 = self.orb.detectAndCompute(g1, None)
        kp2, des2 = self.orb.detectAndCompute(g2, None)
        if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2: return 0
        try: return sum(1.0 / (1.0 + m.distance) for m in sorted(self.bf.match(des1, des2), key=lambda x: x.distance)[:10]) or 0
        except: return 0

    def color_continuity(self, p1, p2, d):
        try:
            hist1 = cv2.calcHist([p1[-1, :]], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256]) if d == 'horizontal' else cv2.calcHist([p1[:, -1]], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            hist2 = cv2.calcHist([p2[0, :]], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256]) if d == 'horizontal' else cv2.calcHist([p2[:, 0]], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
            cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)
            return cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        except: return 0

    def evaluate_arrangement(self, parts, arr):
        s = {'edge': 0, 'feature': 0, 'color': 0}
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for col in range(2):
            t, b = parts[arr[positions.index((0, col))]], parts[arr[positions.index((1, col))]]
            s['edge'] += self.edge_similarity(t, b, 'horizontal')
            s['feature'] += self.feature_similarity(t, b)
            s['color'] += self.color_continuity(t, b, 'horizontal')
        for row in range(2):
            l, r = parts[arr[positions.index((row, 0))]], parts[arr[positions.index((row, 1))]]
            s['edge'] += self.edge_similarity(l, r, 'vertical')
            s['feature'] += self.feature_similarity(l, r)
            s['color'] += self.color_continuity(l, r, 'vertical')
        return s['edge'] * 0.5 + s['feature'] * 0.3 + s['color'] * 0.2

    def solve(self, url):
        try:
            img = self.load(url)
            parts = self.split(img)
            labels = ['A', 'B', 'C', 'D']
            best_score, best_perm = float('-inf'), None
            for perm in itertools.permutations(range(4)):
                try:
                    score = self.evaluate_arrangement(parts, perm)
                    if score > best_score: best_score, best_perm = score, perm
                except: continue
            result = ''.join(labels[i] for i in best_perm) if best_perm else "ABCD"
            alt_results = [result]
            for perm in itertools.permutations(range(4)):
                if perm == best_perm: continue
                try:
                    score = self.evaluate_arrangement(parts, perm)
                    if best_score - score < 0.1 * abs(best_score): alt_results.append(''.join(labels[i] for i in perm))
                except: continue
            return ''.join(reversed(Counter(alt_results).most_common(1)[0][0] if alt_results else result))
        except: return "ABCD"
