"""train_classifier.py - Train a TF-IDF + Logistic Regression classifier for detecting application emails.
Input: CSV with columns 'text' and 'label' (label: 1 for application, 0 for not).
Saves a pickle model 'clf_tfidf.pkl' and vectorizer 'tfidf_vectorizer.pkl' in models/.
"""
import os, pickle
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score

os.makedirs("models", exist_ok=True)
df = pd.read_csv("data/sample_labels.csv")
X = df["text"].fillna("")
y = df["label"].astype(int)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
vec = TfidfVectorizer(ngram_range=(1,2), max_features=5000)
Xtr = vec.fit_transform(X_train)
clf = LogisticRegression(max_iter=1000)
clf.fit(Xtr, y_train)
Xte = vec.transform(X_test)
pred = clf.predict(Xte)
print(classification_report(y_test, pred))
print("Accuracy:", accuracy_score(y_test, pred))
with open("models/tfidf_vectorizer.pkl","wb") as f:
    pickle.dump(vec, f)
with open("models/clf_tfidf.pkl","wb") as f:
    pickle.dump(clf, f)
print("Saved models to models/")