from dataclasses import dataclass, field
from typing import List


@dataclass
class ConversationContext:
    """
    Структурированное состояние текущего обращения пользователя.
    """

    problem: str = ""

    configuration: str = ""

    configuration_version: str = ""

    platform_version: str = ""

    work_mode: str = ""

    database_type: str = ""

    document_type: str = ""

    document_period: str = ""

    error_text: str = ""

    user_actions: List[str] = field(default_factory=list)

    completed_checks: List[str] = field(default_factory=list)

    important_facts: List[str] = field(default_factory=list)

    unresolved_questions: List[str] = field(default_factory=list)

    knowledge_used: List[str] = field(default_factory=list)

    def to_prompt(self) -> str:
        """
        Преобразует состояние обращения в понятный для LLM текст.
        """

        return f"""
ТЕКУЩЕЕ СОСТОЯНИЕ ОБРАЩЕНИЯ

Проблема:
{self.problem or "не определена"}

Конфигурация 1С:
{self.configuration or "не указана"}

Версия конфигурации:
{self.configuration_version or "не указана"}

Версия платформы:
{self.platform_version or "не указана"}

Режим работы:
{self.work_mode or "не указан"}

Тип базы:
{self.database_type or "не указан"}

Вид документа:
{self.document_type or "не указан"}

Период документа:
{self.document_period or "не указан"}

Текст ошибки:
{self.error_text or "не указан"}

Что пользователь уже делал:
{self._format_list(self.user_actions)}

Что уже проверено:
{self._format_list(self.completed_checks)}

Важные факты:
{self._format_list(self.important_facts)}

Незакрытые вопросы:
{self._format_list(self.unresolved_questions)}

Использованная информация из базы знаний:
{self._format_list(self.knowledge_used)}
""".strip()

    @staticmethod
    def _format_list(items: List[str]) -> str:
        if not items:
            return "нет данных"

        return "\n".join(
            f"- {item}"
            for item in items
        )

    def update_problem(self, problem: str):
        if problem:
            self.problem = problem

    def add_user_action(self, action: str):
        if action and action not in self.user_actions:
            self.user_actions.append(action)

    def add_completed_check(self, check: str):
        if check and check not in self.completed_checks:
            self.completed_checks.append(check)

    def add_fact(self, fact: str):
        if fact and fact not in self.important_facts:
            self.important_facts.append(fact)

    def add_unresolved_question(self, question: str):
        if question and question not in self.unresolved_questions:
            self.unresolved_questions.append(question)

    def remove_unresolved_question(self, question: str):
        if question in self.unresolved_questions:
            self.unresolved_questions.remove(question)

    def add_knowledge(self, knowledge: str):
        if knowledge and knowledge not in self.knowledge_used:
            self.knowledge_used.append(knowledge)

    def clear(self):
        """
        Полностью очищает состояние текущего обращения.
        """

        self.problem = ""
        self.configuration = ""
        self.configuration_version = ""
        self.platform_version = ""
        self.work_mode = ""
        self.database_type = ""
        self.document_type = ""
        self.document_period = ""
        self.error_text = ""

        self.user_actions.clear()
        self.completed_checks.clear()
        self.important_facts.clear()
        self.unresolved_questions.clear()
        self.knowledge_used.clear()