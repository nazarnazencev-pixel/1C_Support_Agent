import pytest
from app.agent.agent import SupportAgent


def test_agent_greeting():
    agent = SupportAgent()
    greeting = agent.get_greeting()
    assert "Здравствуйте!" in greeting
    assert "Молвест" in greeting
    assert len(agent.history) == 1
    assert agent.history[0].content == greeting


def test_agent_reset():
    agent = SupportAgent()
    agent.get_greeting()
    agent.reset_conversation()
    assert len(agent.history) == 0
