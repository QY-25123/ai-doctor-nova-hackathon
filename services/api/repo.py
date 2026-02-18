from db import Assessment, Conversation, Message, get_session_factory


def create_conversation() -> int:
    """Create a new conversation. Returns conversation id."""
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        conv = Conversation()
        session.add(conv)
        session.commit()
        session.refresh(conv)
        return conv.id


def add_message(conversation_id: int, role: str, content: str) -> int:
    """Append a message to a conversation. Returns message id."""
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        msg = Message(conversation_id=conversation_id, role=role, content=content)
        session.add(msg)
        session.commit()
        session.refresh(msg)
        return msg.id


def save_assessment(
    conversation_id: int,
    risk_level: str,
    summary: str,
    red_flags_json: str,
    sources_json: str,
) -> int:
    """Save an assessment for a conversation. Returns assessment id."""
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        assessment = Assessment(
            conversation_id=conversation_id,
            risk_level=risk_level,
            summary=summary,
            red_flags_json=red_flags_json,
            sources_json=sources_json,
        )
        session.add(assessment)
        session.commit()
        session.refresh(assessment)
        return assessment.id


def get_conversation_history(conversation_id: int) -> list[dict]:
    """Return messages for a conversation, ordered by created_at. Each item: role, content, created_at (iso)."""
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        messages = (
            session.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .all()
        )
        return [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]
