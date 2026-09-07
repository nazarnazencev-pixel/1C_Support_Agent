import uuid

from app.config.settings import validate_config
from app.gigachat.errors import to_user_message
from app.session.session_manager import SessionManager


def main():
    print("=" * 60)
    print("        1C SUPPORT AI")
    print("=" * 60)

    try:
        validate_config()
    except RuntimeError as error:
        print(f"Ошибка конфигурации: {error}")
        return

    print("Введите 'exit' для выхода.\n")

    # Раньше main.py создавал голый SupportAgent() напрямую -
    # в обход Session/SessionManager/Database. Из-за этого CLI не
    # сохранял обращения в БД и не мог сработать по эскалации при
    # низкой уверенности ответа (Session.ask()). Теперь CLI - это
    # такой же клиент SessionManager, каким должен быть любой
    # реальный канал (веб, Bitrix24 и т.д.).
    manager = SessionManager()
    manager.start_background_cleanup()

    session_id = f"cli-{uuid.uuid4().hex[:8]}"

    try:
        greeting = manager.get_greeting(session_id)
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
                answer = manager.ask(session_id, user_message)

                print("\nAI:")
                print(answer)
                print()

            except Exception as error:
                # to_user_message() вместо str(error) - иначе сюда
                # мог долететь сырой текст исключения (SDK, БД и
                # т.п.) в обход аккуратных сообщений об ошибках.
                print("\nОшибка:")
                print(to_user_message(error))
                print()
    finally:
        manager.shutdown()


if __name__ == "__main__":
    main()
