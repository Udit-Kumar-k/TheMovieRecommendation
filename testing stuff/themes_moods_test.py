from transformers import pipeline

classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

overview = """
Dr. Vaseegaran creates Chitti, a powerful robot in his own image, but it is rejected by the scientific body AIRD due to its lack of human behaviour and emotions. After a lightning strike triggers emotions in Chitti, he begins to develop human-like feelings. However, Chitti falls in love with Dr. Vaseegaran’s fiancée, Sana, and turns against his creator, leading to dangerous consequences.
"""

themes = [
    "coming of age", "grief", "supernatural", "redemption", "family drama", "love triangle", "dystopian", "philosophical", "revenge"
]

moods = [
    "dark", "sad", "hopeful", "mysterious", "uplifting", "tense", "wholesome"
]

# Run both separately or together
themes_result = classifier(overview, themes, multi_label=True)
moods_result = classifier(overview, moods, multi_label=True)

print("\n🎭 THEMES:")
for label, score in zip(themes_result['labels'], themes_result['scores']):
    print(f"{label}: {score:.2f}")

print("\n🎨 MOODS:")
for label, score in zip(moods_result['labels'], moods_result['scores']):
    print(f"{label}: {score:.2f}")
