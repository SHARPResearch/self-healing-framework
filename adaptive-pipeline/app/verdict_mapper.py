"""
verdict_mapper.py
The "Translator" for Component 3.
Converts LiyanaArachchi's Shadow Mode verdict strings into numerical RL multipliers.
"""

class VerdictMapper:
    # Maps DB verdict strings to numerical reward multipliers
    VERDICT_MULTIPLIERS = {
        "ACTION_WOULD_HAVE_HELPED": 1.0,
        "ACTION_WOULD_HAVE_BEEN_NEUTRAL": 0.5,
        "ACTION_WOULD_HAVE_BEEN_UNNECESSARY": 0.0,
        "HARMFUL": -1.0,
        "UNKNOWN": 0.0
    }

    def get_multiplier(self, verdict: str) -> float:
        """
        Returns the numerical multiplier for a given shadow verdict.
        Defaults to 0.0 if the verdict is unrecognized.
        """
        if not verdict:
            return 0.0
        # Clean up the string to match keys exactly
        clean_verdict = verdict.strip().upper()
        return self.VERDICT_MULTIPLIERS.get(clean_verdict, 0.0)