from app.context.context import (
    ConversationContext,
    ConversationStatus,
)


class ContextManager:
    """
    Управляет структурированным состоянием обращения.

    ContextManager является промежуточным слоем
    между SupportAgent и ConversationContext.

    SupportAgent не должен самостоятельно изменять
    внутреннее состояние ConversationContext там,
    где для этого существует метод ContextManager.
    """

    def __init__(
        self,
        context: ConversationContext,
    ):
        self.context = context

    # =========================================================
    # Проблема
    # =========================================================

    def update_problem(
        self,
        problem: str,
    ):
        self.context.update_problem(problem)

    # =========================================================
    # Категория
    # =========================================================

    def update_category(
        self,
        category: str,
    ):
        self.context.update_category(category)

    # =========================================================
    # Информация о 1С
    # =========================================================

    def update_configuration(
        self,
        configuration: str,
    ):
        self.context.update_configuration(
            configuration
        )

    def update_configuration_version(
        self,
        version: str,
    ):
        self.context.update_configuration_version(
            version
        )

    def update_platform_version(
        self,
        version: str,
    ):
        self.context.update_platform_version(
            version
        )

    def update_work_mode(
        self,
        work_mode: str,
    ):
        self.context.update_work_mode(
            work_mode
        )

    def update_database_type(
        self,
        database_type: str,
    ):
        self.context.update_database_type(
            database_type
        )

    # =========================================================
    # Документ
    # =========================================================

    def update_document_type(
        self,
        document_type: str,
    ):
        self.context.update_document_type(
            document_type
        )

    def update_document_period(
        self,
        period: str,
    ):
        self.context.update_document_period(
            period
        )

    # =========================================================
    # Ошибка
    # =========================================================

    def update_error(
        self,
        error_text: str,
        error_code: str = "",
    ):
        self.context.update_error(
            error_text=error_text,
            error_code=error_code,
        )

    # =========================================================
    # Действия пользователя
    # =========================================================

    def add_user_action(
        self,
        action: str,
    ):
        self.context.add_user_action(action)

    # =========================================================
    # Проверки
    # =========================================================

    def add_check(
        self,
        check: str,
    ):
        self.context.add_completed_check(check)

    # =========================================================
    # Факты
    # =========================================================

    def add_fact(
        self,
        fact: str,
    ):
        self.context.add_fact(fact)

    # =========================================================
    # Незакрытые вопросы
    # =========================================================

    def add_question(
        self,
        question: str,
    ):
        self.context.add_unresolved_question(
            question
        )

    def resolve_question(
        self,
        question: str,
    ):
        self.context.remove_unresolved_question(
            question
        )

    # =========================================================
    # Исключённые гипотезы
    # =========================================================

    def exclude_hypothesis(
        self,
        hypothesis: str,
    ):
        self.context.add_excluded_hypothesis(
            hypothesis
        )

    # =========================================================
    # Гипотеза
    # =========================================================

    def set_hypothesis(
        self,
        hypothesis: str,
        confidence: float | None = None,
    ):
        self.context.set_hypothesis(
            hypothesis=hypothesis,
            confidence=confidence,
        )

    def clear_hypothesis(self):
        self.context.clear_hypothesis()

    # =========================================================
    # Диагностический цикл
    # =========================================================

    def new_diagnostic_cycle(self):
        self.context.start_diagnostic_cycle()

    # =========================================================
    # Следующее действие
    # =========================================================

    def set_next_action(
        self,
        action: str,
    ):
        self.context.set_next_action(action)

    # =========================================================
    # База знаний
    # =========================================================

    def add_knowledge(
        self,
        knowledge: str,
    ):
        self.context.add_knowledge(knowledge)

    # =========================================================
    # Вложения
    # =========================================================

    def add_attachment(
        self,
        file_name: str,
        file_id: str = "",
        file_type: str = "",
        analysis: str = "",
    ):
        self.context.add_attachment(
            file_name=file_name,
            file_id=file_id,
            file_type=file_type,
            analysis=analysis,
        )

    def add_file_analysis(
        self,
        file_path: str,
        analysis: str,
        file_id: str = "",
        file_type: str = "",
    ):
        """
        Сохраняет результат анализа файла.

        Сам файл не помещается в Context.
        """

        self.context.add_attachment(
            file_name=file_path,
            file_id=file_id,
            file_type=file_type,
            analysis=analysis,
        )

    # =========================================================
    # Статус
    # =========================================================

    def set_status(
        self,
        status: ConversationStatus,
    ):
        self.context.set_status(status)

    def start_diagnosis(self):
        self.context.set_status(
            ConversationStatus.DIAGNOSING
        )

    def wait_user(self):
        self.context.set_status(
            ConversationStatus.WAITING_USER
        )

    def start_solving(self):
        self.context.set_status(
            ConversationStatus.SOLVING
        )

    # =========================================================
    # Эскалация
    # =========================================================

    def escalate(
        self,
        reason: str,
    ):
        self.context.escalate(reason)

    # =========================================================
    # Решение
    # =========================================================

    def mark_solved(
        self,
        resolution: str,
    ):
        self.context.mark_solved(resolution)

    # =========================================================
    # Очистка
    # =========================================================

    def clear(self):
        self.context.clear()