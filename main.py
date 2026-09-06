from app.agent.agent import SupportAgent


def main():
    print("=" * 60)
    print("        1C SUPPORT AI")
    print("=" * 60)
    print("Введите 'exit' для выхода.\n")

    agent = SupportAgent()

    # Сразу же представляемся пользователю
    greeting = agent.get_greeting()
    print("AI:")
    print(greeting)
    print()

    while True:
        user_message = input("Вы: ")

        if user_message.lower() == "exit":
            print("До свидания!")
            break

        if not user_message.strip():
            continue

        try:
            answer = agent.ask(user_message)

            print("\nAI:")
            print(answer)
            print()

        except Exception as error:
            print("\nОшибка:")
            print(error)
            print()


if __name__ == "__main__":
    main()