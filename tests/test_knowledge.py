from app.knowledge.base import LocalKnowledgeBase


kb = LocalKnowledgeBase()

results = kb.search(
    "не проводится документ в 1С"
)

print("Найдено документов:", len(results))

for result in results:
    print()
    print("Файл:", result["file"])
    print("Рейтинг:", result["score"])
    print("Содержимое:")
    print(result["content"])