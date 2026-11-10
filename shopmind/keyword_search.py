"""Keyword search written from scratch: TF-IDF and BM25.

Weaviate already has BM25 built in. These versions exist so you can see what
happens inside, and compare them with Weaviate's results in the evaluation.

Both work on the same chunks that are stored in Weaviate.
"""
import math
import re
from collections import Counter

import numpy as np

STOPWORDS = set("""a an and are as at be by can do does for from has have how i if in is it its me my
of on or our so that the their them there this to was we what when where which who will with you your""".split())


def tokenize(text: str) -> list[str]:
    """Lowercase, keep letters and digits, drop very common words."""
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


class TfidfIndex:
    """TF-IDF with cosine similarity.

    tf  = how often a word appears in this chunk (log-scaled: 1 + log(count))
    idf = how rare the word is across all chunks: log(N / df) + 1
    A chunk's vector holds tf * idf for each word; the score is the cosine
    between the query vector and the chunk vector.
    """

    def __init__(self, texts: list[str]):
        docs = [Counter(tokenize(t)) for t in texts]
        self.vocab = {w: i for i, w in enumerate(sorted({w for d in docs for w in d}))}
        n = len(docs)
        df = Counter(w for d in docs for w in d)
        self.idf = np.zeros(len(self.vocab))
        for w, i in self.vocab.items():
            self.idf[i] = math.log(n / df[w]) + 1
        self.matrix = np.vstack([self._vector(d) for d in docs])

    def _vector(self, counts: Counter) -> np.ndarray:
        v = np.zeros(len(self.vocab))
        for w, c in counts.items():
            if w in self.vocab:
                v[self.vocab[w]] = (1 + math.log(c)) * self.idf[self.vocab[w]]
        norm = np.linalg.norm(v)
        return v / norm if norm else v

    def scores(self, query: str) -> np.ndarray:
        return self.matrix @ self._vector(Counter(tokenize(query)))


class BM25Index:
    """Okapi BM25, the formula Weaviate and most search engines use.

    score(q, d) = sum over query words w of
        idf(w) * tf(w, d) * (k1 + 1) / (tf(w, d) + k1 * (1 - b + b * len(d) / avg_len))

    k1 controls how quickly repeating a word stops helping (saturation).
    b  controls how much long chunks are penalised (length normalisation).
    """

    def __init__(self, texts: list[str], k1: float = 1.2, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(t)) for t in texts]
        self.lengths = np.array([sum(d.values()) for d in self.docs])
        self.avg_len = self.lengths.mean()
        n = len(self.docs)
        df = Counter(w for d in self.docs for w in d)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    def scores(self, query: str) -> np.ndarray:
        out = np.zeros(len(self.docs))
        for w in set(tokenize(query)):
            if w not in self.idf:
                continue
            tf = np.array([d[w] for d in self.docs])
            norm = self.k1 * (1 - self.b + self.b * self.lengths / self.avg_len)
            out += self.idf[w] * tf * (self.k1 + 1) / (tf + norm)
        return out
