"""Deterministic rules for multi-turn conversations.

No model is involved. Every decision here can be read, tested and explained:
which slot was inherited, from how many turns ago, and why.

RESOLVE (fill the current turn from the stored state)
  1. A slot the user stated in this turn always wins.
  2. An empty slot is inherited if the intent requires it, or if the turn is a
     follow-up fragment.
  3. A follow-up also inherits the previous intent, unless what it mentions
     cannot belong to that intent (a disaster after a weather question).
     A follow-up is an entity-only fragment, or a query that adds only a
     place or a time while the classifier is unsure of its intent.
  4. Nothing is inherited that was last stated too many turns ago.
  5. Every inherited field is listed in `context_used`.

UPDATE (store the turn for later)
  6. Out-of-domain and scenario turns leave the stored state untouched.
  7. Only slots the user STATED refresh their age; inherited ones keep ageing.
"""

from backend.core.config import ContextConfig
from backend.nlp.context.state import ConversationState, ResolvedTurn, TurnParse
from backend.nlp.query.enums import Intent
from backend.nlp.query.intents import INTENT_SPECS

_TAKES_DISASTERS = {
    Intent.DISASTER_RISK, Intent.COMPARISON, Intent.SCENARIO_ANALYSIS, Intent.GENERAL_ENVIRONMENT,
}
# Turns that must not become the context for later follow-ups: a hypothetical
# is not the topic of conversation, and an off-topic remark has no slots.
_NOT_STORED = {Intent.OUT_OF_DOMAIN, Intent.SCENARIO_ANALYSIS}


class ContextResolver:
    def __init__(self, config: ContextConfig) -> None:
        self._config = config

    def _fresh(self, state: ConversationState, slot: str) -> bool:
        """Was this slot stated recently enough to be inherited now?"""
        stated = state.stated_at.get(slot)
        if stated is None:
            return False
        current_turn = state.turn_count + 1
        return current_turn - stated <= self._config.max_slot_age_turns

    def resolve(self, turn: TurnParse, state: ConversationState | None) -> ResolvedTurn:
        resolved = ResolvedTurn(
            language=turn.language, intent=turn.intent,
            locations=turn.locations, variables=turn.variables, disasters=turn.disasters,
            time_period=turn.time_period, scenario=turn.scenario, target=turn.target,
        )
        if state is None or state.intent is None:
            return resolved

        # An unsure classification of a query that only adds a place or a time
        # ("how will it be tomorrow?") is more likely a continuation of the
        # conversation than a new topic.
        # It must not name its own topic, though: "Show the NDVI trend in
        # Namchi" with a shaky classification is a new question to ask about,
        # not a continuation.
        adds_detail = bool(turn.locations or turn.time_period)
        names_topic = bool(turn.variables or turn.disasters)
        unsure_followup = not turn.intent_confident and adds_detail and not names_topic
        if turn.intent is Intent.OUT_OF_DOMAIN and not unsure_followup:
            return resolved

        used: list[str] = []
        followup = turn.is_fragment or unsure_followup
        resolved.is_followup = followup

        if followup:
            if turn.disasters and not turn.variables and state.intent not in _TAKES_DISASTERS:
                # "And landslides?" after a weather question is a new topic.
                resolved.intent = Intent.DISASTER_RISK
            elif turn.variables and not turn.disasters and state.intent is Intent.DISASTER_RISK:
                # "What about rainfall?" after a risk question.
                resolved.intent = (
                    turn.intent
                    if turn.intent not in (Intent.DISASTER_RISK, Intent.OUT_OF_DOMAIN)
                    else Intent.WEATHER_QUERY
                )
            else:
                resolved.intent = state.intent
                used.append("intent")

        required = set().union(*INTENT_SPECS[resolved.intent].required)

        if not turn.locations and state.locations and self._fresh(state, "locations"):
            if followup or "locations" in required:
                resolved.locations = state.locations
                used.append("locations")

        # Variables and disasters are one question: "what is this about?".
        # They are inherited only if the turn names neither.
        if not turn.variables and not turn.disasters:
            for slot in ("variables", "disasters"):
                stored = getattr(state, slot)
                if stored and self._fresh(state, slot) and (followup or slot in required):
                    setattr(resolved, slot, stored)
                    used.append(slot)

        # A time span carries over only to a follow-up. A complete new
        # question without a time means "no particular time".
        if turn.time_period is None and followup and self._fresh(state, "time_period"):
            if state.time_period is not None:
                resolved.time_period = state.time_period
                used.append("time_period")

        resolved.context_used = used
        return resolved

    def update(self, state: ConversationState | None, turn: TurnParse,
               resolved: ResolvedTurn, now: float) -> ConversationState:
        """State to store after this turn."""
        state = (state or ConversationState()).model_copy(deep=True)
        state.turn_count += 1
        state.updated_at = now
        state.language = resolved.language
        if resolved.intent in _NOT_STORED:
            return state

        state.intent = resolved.intent
        current = state.turn_count

        if turn.locations:
            state.locations = turn.locations
            state.stated_at["locations"] = current

        if turn.variables or turn.disasters:
            # Replace the pair together, so an old disaster cannot linger
            # beside a newly stated variable.
            state.variables, state.disasters = turn.variables, turn.disasters
            state.stated_at["variables"] = state.stated_at["disasters"] = current

        if turn.time_period is not None:
            state.time_period = turn.time_period
            state.stated_at["time_period"] = current
        elif not resolved.is_followup:
            state.time_period = None
            state.stated_at.pop("time_period", None)

        return state
