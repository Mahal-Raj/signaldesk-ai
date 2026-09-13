import re
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity

from .data import EXAMPLES, INCIDENTS, RUNBOOKS

PII_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"), "[EMAIL REDACTED]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP REDACTED]"),
    (re.compile(r"(?i)\b(?:api[_ -]?key|token|password)\s*[:=]\s*\S+"), "[SECRET REDACTED]"),
]

# Fixed operational vocabulary adds domain knowledge while the statistical model
# handles phrasing and uncertainty. Phrases are intentionally versioned and auditable.
DOMAIN_LEXICON = {
    "database": ("postgres", "database", "sql", "query", "replica", "redis", "rds", "deadlock", "connection pool", "mongodb"),
    "network": ("subnet", "packet loss", "dns", "load balancer", "vpn", "firewall rule", "service mesh", "nat gateway", "ingress", "connection reset"),
    "authentication": ("sign in", "login", "oauth", "saml", "jwt", "identity provider", "access denied", "session", "refresh token", "redirect uri"),
    "deployment": ("release", "rollout", "canary", "helm", "deployment", "rollback", "image tag", "feature flag", "github actions", "deployed configuration"),
    "compute": ("oom", "out of memory", "cpu pressure", "autoscaler", "capacity", "worker", "serverless", "concurrency", "memory", "crash loop"),
    "security": ("leaked", "compromised", "malware", "made public", "secret scanner", "credentials", "privilege escalation", "private key", "ransomware", "suspicious", "injection"),
}

@dataclass
class Analysis:
    redacted_text: str
    category: str
    confidence: float
    severity: str
    team: str
    runbook: str
    evidence: list[str]
    similar: list[dict]

class IncidentEngine:
    def __init__(self, texts=None, labels=None):
        self.labels, self.texts = labels or [], texts or []
        if not texts:
            for label, examples in EXAMPLES.items():
                self.labels.extend([label] * len(examples))
                self.texts.extend(examples)
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)
        matrix = self.vectorizer.fit_transform(self.texts)
        self.model = LogisticRegression(max_iter=1500, C=5, random_state=42).fit(matrix, self.labels)
        self.incident_matrix = self.vectorizer.transform([item["text"] for item in INCIDENTS])

    @staticmethod
    def redact(text):
        result, count = text, 0
        for pattern, replacement in PII_PATTERNS:
            result, hits = pattern.subn(replacement, result)
            count += hits
        return result, count

    def analyze(self, text):
        if not isinstance(text, str) or len(text.strip()) < 12:
            raise ValueError("Describe the incident in at least 12 characters")
        if len(text) > 4000:
            raise ValueError("Incident description must be under 4,000 characters")
        redacted, _ = self.redact(text.strip())
        vector = self.vectorizer.transform([redacted])
        probabilities = self._hybrid_probabilities(redacted, vector)
        ranked = sorted(zip(self.model.classes_, probabilities), key=lambda pair: pair[1], reverse=True)
        category, confidence = ranked[0]
        similarities = cosine_similarity(vector, self.incident_matrix)[0]
        matches = sorted(zip(INCIDENTS, similarities), key=lambda pair: pair[1], reverse=True)[:3]
        terms = self._evidence(vector, category)
        severity = self._severity(redacted, confidence)
        team = {"security": "Security Operations", "authentication": "Identity Platform", "database": "Data Platform", "network": "Cloud Networking", "compute": "Platform Engineering", "deployment": "Release Engineering"}[category]
        return Analysis(redacted, category, round(float(confidence), 3), severity, team, RUNBOOKS[category], terms, [dict(item, similarity=round(float(score), 3)) for item, score in matches])

    def predict(self, texts):
        return [self.model.classes_[self._hybrid_probabilities(text, self.vectorizer.transform([text])).argmax()] for text in texts]

    def _hybrid_probabilities(self, text, vector):
        probabilities = self.model.predict_proba(vector)[0]
        lowered = text.lower()
        for label, phrases in DOMAIN_LEXICON.items():
            hits = sum(1 for phrase in phrases if phrase in lowered)
            probabilities[list(self.model.classes_).index(label)] += min(.72, hits * .24)
        return probabilities / probabilities.sum()

    def _evidence(self, vector, category):
        row = self.model.coef_[list(self.model.classes_).index(category)]
        names = self.vectorizer.get_feature_names_out()
        indices = vector.nonzero()[1]
        ranked = sorted(indices, key=lambda idx: row[idx] * vector[0, idx], reverse=True)
        return [names[idx] for idx in ranked if row[idx] > 0][:5]

    @staticmethod
    def _severity(text, confidence):
        lowered = text.lower()
        critical = ("all users", "production", "leaked", "public", "ransomware", "data loss")
        high = ("failing", "timeout", "unreachable", "denied", "crash", "five hundred")
        if any(word in lowered for word in critical): return "SEV-1"
        if any(word in lowered for word in high) or confidence >= .65: return "SEV-2"
        return "SEV-3"
