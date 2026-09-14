from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConversationStatus(str, Enum):
    """
    Состояние текущего обращения.
    """

    NEW = "new"

    DIAGNOSING = "diagnosing"

    WAITING_USER = "waiting_user"

    SOLVING = "solving"

    SOLVED = "solved"

    ESCALATED = "escalated"

    CLOSED = "closed"


@dataclass
class ConversationContext:
    """
    Структурированное состояние одного обращения.

    ВАЖНО:

    ConversationContext НЕ хранит историю сообщений.

    История находится в:
        SupportAgent.history

    ConversationContext хранит только текущее понимание
    проблемы агентом.
    """

    # =========================================================
    # Состояние
    # =========================================================

    status: ConversationStatus = ConversationStatus.NEW

    # =========================================================
    # Проблема
    # =========================================================

    problem: str = ""

    # =========================================================
    # Категория обращения
    # =========================================================

    category: str = ""

    # =========================================================
    # Информация о 1С
    # =========================================================

    configuration: str = ""

    configuration_version: str = ""

    platform_version: str = ""

    work_mode: str = ""

    database_type: str = ""

    # =========================================================
    # Документ / операция
    # =========================================================

    document_type: str = ""

    document_period: str = ""

    # =========================================================
    # Ошибка
    # =========================================================

    error_text: str = ""

    error_code: str = ""

    # =========================================================
    # Диагностика
    # =========================================================

    user_actions: list[str] = field(
        default_factory=list
    )

    completed_checks: list[str] = field(
        default_factory=list
    )

    important_facts: list[str] = field(
        default_factory=list
    )

    unresolved_questions: list[str] = field(
        default_factory=list
    )

    excluded_hypotheses: list[str] = field(
        default_factory=list
    )

    # =========================================================
    # Гипотеза
    # =========================================================

    current_hypothesis: str = ""

    hypothesis_confidence: float = 0.0

    diagnostic_cycle: int = 0

    # =========================================================
    # Следующее действие
    # =========================================================

    next_action: str = ""

    # =========================================================
    # База знаний
    # =========================================================

    knowledge_used: list[str] = field(
        default_factory=list
    )

    # =========================================================
    # Вложения
    # =========================================================

    attachments: list[dict[str, Any]] = field(
        default_factory=list
    )

    # =========================================================
    # Эскалация
    # =========================================================

    escalation_reason: str = ""

    # =========================================================
    # Результат
    # =========================================================

    resolution: str = ""

    resolution_confirmed: bool = False

    # =========================================================
    # Проблема
    # =========================================================

    def update_problem(
        self,
        problem: str,
    ) -> None:

        if problem:
            self.problem = problem

    # =========================================================
    # Категория
    # =========================================================

    def update_category(
        self,
        category: str,
    ) -> None:

        if category:
            self.category = category

    # =========================================================
    # 1С
    # =========================================================

    def update_configuration(
        self,
        configuration: str,
    ) -> None:

        if configuration:
            self.configuration = configuration

    def update_configuration_version(
        self,
        version: str,
    ) -> None:

        if version:
            self.configuration_version = version

    def update_platform_version(
        self,
        version: str,
    ) -> None:

        if version:
            self.platform_version = version

    def update_work_mode(
        self,
        work_mode: str,
    ) -> None:

        if work_mode:
            self.work_mode = work_mode

    def update_database_type(
        self,
        database_type: str,
    ) -> None:

        if database_type:
            self.database_type = database_type

    # =========================================================
    # Документ
    # =========================================================

    def update_document_type(
        self,
        document_type: str,
    ) -> None:

        if document_type:
            self.document_type = document_type

    def update_document_period(
        self,
        period: str,
    ) -> None:

        if period:
            self.document_period = period

    # =========================================================
    # Ошибка
    # =========================================================

    def update_error(
        self,
        error_text: str,
        error_code: str = "",
    ) -> None:

        if error_text:
            self.error_text = error_text

        if error_code:
            self.error_code = error_code

    # =========================================================
    # Действия
    # =========================================================

    def add_user_action(
        self,
        action: str,
    ) -> None:

        if (
            action
            and action not in self.user_actions
        ):
            self.user_actions.append(action)

    # =========================================================
    # Проверки
    # =========================================================

    def add_completed_check(
        self,
        check: str,
    ) -> None:

        if (
            check
            and check not in self.completed_checks
        ):
            self.completed_checks.append(check)

    # =========================================================
    # Факты
    # =========================================================

    def add_fact(
        self,
        fact: str,
    ) -> None:

        if (
            fact
            and fact not in self.important_facts
        ):
            self.important_facts.append(fact)

    # =========================================================
    # Незакрытые вопросы
    # =========================================================

    def add_unresolved_question(
        self,
        question: str,
    ) -> None:

        if (
            question
            and question not in self.unresolved_questions
        ):
            self.unresolved_questions.append(question)

    def remove_unresolved_question(
        self,
        question: str,
    ) -> None:

        if question in self.unresolved_questions:
            self.unresolved_questions.remove(
                question
            )

    # =========================================================
    # Исключённые гипотезы
    # =========================================================

    def add_excluded_hypothesis(
        self,
        hypothesis: str,
    ) -> None:

        if (
            hypothesis
            and hypothesis not in self.excluded_hypotheses
        ):
            self.excluded_hypotheses.append(
                hypothesis
            )

    # =========================================================
    # Гипотеза
    # =========================================================

    def set_hypothesis(
        self,
        hypothesis: str,
        confidence: float | None = None,
    ) -> None:

        if hypothesis:
            self.current_hypothesis = hypothesis

        if confidence is not None:

            self.hypothesis_confidence = max(
                0.0,
                min(1.0, confidence),
            )

    def clear_hypothesis(self) -> None:

        self.current_hypothesis = ""

        self.hypothesis_confidence = 0.0

    # =========================================================
    # Диагностический цикл
    # =========================================================

    def start_diagnostic_cycle(self) -> None:

        self.diagnostic_cycle += 1

    # =========================================================
    # Следующее действие
    # =========================================================

    def set_next_action(
        self,
        action: str,
    ) -> None:

        self.next_action = action

    # =========================================================
    # База знаний
    # =========================================================

    def add_knowledge(
        self,
        knowledge: str,
    ) -> None:

        if (
            knowledge
            and knowledge not in self.knowledge_used
        ):
            self.knowledge_used.append(
                knowledge
            )

    # =========================================================
    # Вложения
    # =========================================================

    def add_attachment(
        self,
        file_name: str,
        file_id: str = "",
        file_type: str = "",
        analysis: str = "",
    ) -> None:

        if not file_name:
            return

        for attachment in self.attachments:

            if (
                attachment.get("file_name")
                == file_name
            ):

                if file_id:
                    attachment["file_id"] = file_id

                if file_type:
                    attachment["file_type"] = file_type

                if analysis:
                    attachment["analysis"] = analysis

                return

        self.attachments.append(
            {
                "file_name": file_name,
                "file_id": file_id,
                "file_type": file_type,
                "analysis": analysis,
            }
        )

    # =========================================================
    # Эскалация
    # =========================================================

    def escalate(
        self,
        reason: str,
    ) -> None:

        self.status = (
            ConversationStatus.ESCALATED
        )

        self.escalation_reason = reason

    # =========================================================
    # Решение
    # =========================================================

    def mark_solved(
        self,
        resolution: str,
    ) -> None:

        self.status = (
            ConversationStatus.SOLVED
        )

        self.resolution = resolution

        self.resolution_confirmed = True

    # =========================================================
    # Статус
    # =========================================================

    def set_status(
        self,
        status: ConversationStatus,
    ) -> None:

        self.status = status

    # =========================================================
    # Форматирование
    # =========================================================

    @staticmethod
    def _format_list(
        items: list[str],
    ) -> str:

        if not items:
            return "нет данных"

        return "\n".join(
            f"- {item}"
            for item in items
        )

    def _format_attachments(self) -> str:

        if not self.attachments:
            return "нет вложений"

        result = []

        for attachment in self.attachments:

            file_name = attachment.get(
                "file_name",
                "неизвестный файл",
            )

            file_type = attachment.get(
                "file_type",
                "",
            )

            analysis = attachment.get(
                "analysis",
                "",
            )

            line = f"- {file_name}"

            if file_type:
                line += f" ({file_type})"

            if analysis:
                line += (
                    f"\n  Анализ: {analysis}"
                )

            result.append(line)

        return "\n".join(result)

    # =========================================================
    # Prompt
    # =========================================================

    def to_prompt(self) -> str:

        confidence = (
            f"{self.hypothesis_confidence * 100:.0f}%"
            if self.current_hypothesis
            else "не определена"
        )

        return f"""
ТЕКУЩЕЕ СОСТОЯНИЕ ОБРАЩЕНИЯ

Статус:
{self.status.value}

Проблема:
{self.problem or "не определена"}

ИНФОРМАЦИЯ О 1С

Конфигурация:
{self.configuration or "не указана"}

Версия конфигурации:
{self.configuration_version or "не указана"}

Версия платформы:
{self.platform_version or "не указана"}

Режим работы:
{self.work_mode or "не указан"}

Тип информационной базы:
{self.database_type or "не указан"}

ДАННЫЕ ДОКУМЕНТА

Вид документа:
{self.document_type or "не указан"}

Период документа:
{self.document_period or "не указан"}

ОШИБКА

Текст ошибки:
{self.error_text or "не указан"}

Код ошибки:
{self.error_code or "не указан"}

ДИАГНОСТИКА

Что пользователь уже делал:
{self._format_list(self.user_actions)}

Что уже проверено:
{self._format_list(self.completed_checks)}

Важные факты:
{self._format_list(self.important_facts)}

Незакрытые вопросы:
{self._format_list(self.unresolved_questions)}

Исключённые гипотезы:
{self._format_list(self.excluded_hypotheses)}

Текущая гипотеза:
{self.current_hypothesis or "не сформирована"}

Уверенность в гипотезе:
{confidence}

Количество диагностических циклов:
{self.diagnostic_cycle}

Следующее действие:
{self.next_action or "не определено"}

ВЛОЖЕНИЯ

{self._format_attachments()}

БАЗА ЗНАНИЙ

Использованная информация:
{self._format_list(self.knowledge_used)}

ЭСКАЛАЦИЯ

Причина передачи оператору:
{self.escalation_reason or "не требуется"}

РЕЗУЛЬТАТ

Решение:
{self.resolution or "не определено"}

Проблема подтверждённо решена:
{"да" if self.resolution_confirmed else "нет"}
""".strip()

    # =========================================================
    # Сериализация
    # =========================================================

    def to_dict(self) -> dict[str, Any]:

        return {
            "status": self.status.value,
            "problem": self.problem,
            "category": self.category,
            "configuration": self.configuration,
            "configuration_version":
                self.configuration_version,
            "platform_version":
                self.platform_version,
            "work_mode": self.work_mode,
            "database_type": self.database_type,
            "document_type": self.document_type,
            "document_period": self.document_period,
            "error_text": self.error_text,
            "error_code": self.error_code,
            "user_actions": list(self.user_actions),
            "completed_checks":
                list(self.completed_checks),
            "important_facts":
                list(self.important_facts),
            "unresolved_questions":
                list(self.unresolved_questions),
            "excluded_hypotheses":
                list(self.excluded_hypotheses),
            "current_hypothesis":
                self.current_hypothesis,
            "hypothesis_confidence":
                self.hypothesis_confidence,
            "diagnostic_cycle":
                self.diagnostic_cycle,
            "next_action":
                self.next_action,
            "knowledge_used":
                list(self.knowledge_used),
            "attachments": [
                dict(attachment)
                for attachment in self.attachments
            ],
            "escalation_reason":
                self.escalation_reason,
            "resolution":
                self.resolution,
            "resolution_confirmed":
                self.resolution_confirmed,
        }

    def restore_from_dict(
        self,
        data: dict[str, Any],
    ) -> None:
        """
        Восстанавливает состояние из словаря, полученного
        через to_dict() (например, после десериализации из Redis).

        Единая точка восстановления - раньше это делалось вручную
        по месту (RedisSessionManager._hydrate_session_from_redis)
        и восстанавливало только 4 поля из примерно двадцати,
        включая пропущенный status - после восстановления сессии
        из Redis статус (например ESCALATED/SOLVED) терялся.

        Отсутствующие в data ключи не трогают текущее значение
        поля.
        """

        if "status" in data:
            try:
                self.status = ConversationStatus(
                    data["status"]
                )
            except ValueError:
                pass

        string_fields = (
            "problem",
            "category",
            "configuration",
            "configuration_version",
            "platform_version",
            "work_mode",
            "database_type",
            "document_type",
            "document_period",
            "error_text",
            "error_code",
            "current_hypothesis",
            "next_action",
            "escalation_reason",
            "resolution",
        )

        for name in string_fields:
            if name in data and isinstance(
                data[name], str
            ):
                setattr(self, name, data[name])

        list_fields = (
            "user_actions",
            "completed_checks",
            "important_facts",
            "unresolved_questions",
            "excluded_hypotheses",
            "knowledge_used",
        )

        for name in list_fields:
            if name in data and isinstance(
                data[name], list
            ):
                setattr(
                    self,
                    name,
                    [
                        item
                        for item in data[name]
                        if isinstance(item, str)
                    ],
                )

        if "hypothesis_confidence" in data and isinstance(
            data["hypothesis_confidence"], (int, float)
        ):
            self.hypothesis_confidence = max(
                0.0,
                min(1.0, float(data["hypothesis_confidence"])),
            )

        if "diagnostic_cycle" in data and isinstance(
            data["diagnostic_cycle"], int
        ):
            self.diagnostic_cycle = data["diagnostic_cycle"]

        if "resolution_confirmed" in data and isinstance(
            data["resolution_confirmed"], bool
        ):
            self.resolution_confirmed = data[
                "resolution_confirmed"
            ]

        if "attachments" in data and isinstance(
            data["attachments"], list
        ):
            self.attachments = [
                dict(item)
                for item in data["attachments"]
                if isinstance(item, dict)
            ]

    # =========================================================
    # Очистка
    # =========================================================

    def clear(self) -> None:

        self.status = ConversationStatus.NEW

        self.problem = ""

        self.category = ""

        self.configuration = ""

        self.configuration_version = ""

        self.platform_version = ""

        self.work_mode = ""

        self.database_type = ""

        self.document_type = ""

        self.document_period = ""

        self.error_text = ""

        self.error_code = ""

        self.user_actions.clear()

        self.completed_checks.clear()

        self.important_facts.clear()

        self.unresolved_questions.clear()

        self.excluded_hypotheses.clear()

        self.current_hypothesis = ""

        self.hypothesis_confidence = 0.0

        self.diagnostic_cycle = 0

        self.next_action = ""

        self.knowledge_used.clear()

        self.attachments.clear()

        self.escalation_reason = ""

        self.resolution = ""

        self.resolution_confirmed = False