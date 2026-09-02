from app.agent.agent import SupportAgent


agent = SupportAgent()

result = agent.analyze_file(
    "data/test_error.png",
    "Проанализируй этот скриншот. Определи текст ошибки 1С и объясни, что она означает."
)

print("\nРезультат анализа:\n")
print(result)