"""
shadow_report_formatter.py
The "Shadow Report Card" for Component 3.
Formats raw shadow mode data into a clean JSON structure for the LLM Copilot (Component 4).
"""

class ShadowReportFormatter:
    def format_for_llm(self, shadow_results: list) -> dict:
        """
        Takes a list of raw shadow results and formats them into a 
        structured dictionary optimized for LLM context injection.
        """
        if not shadow_results:
            return {"status": "no_shadow_data", "summary": "No shadow mode records found."}

        total_reward = sum(r.get('counterfactual_reward', 0.0) for r in shadow_results)
        avg_reward = total_reward / len(shadow_results)
        
        # Count how many actions would have been helpful vs harmful
        helpful_count = sum(1 for r in shadow_results if r.get('counterfactual_reward', 0) > 0)
        harmful_count = sum(1 for r in shadow_results if r.get('counterfactual_reward', 0) < 0)

        return {
            "status": "shadow_analysis_complete",
            "total_records_analyzed": len(shadow_results),
            "aggregate_metrics": {
                "total_counterfactual_reward": float(total_reward),
                "average_reward_per_action": float(avg_reward),
                "helpful_actions_count": helpful_count,
                "harmful_actions_count": harmful_count
            },
            "detailed_traces": shadow_results,
            "llm_summary_prompt": f"Analyzed {len(shadow_results)} shadow actions. {helpful_count} would have helped, {harmful_count} would have harmed. Average reward: {avg_reward:.2f}."
        }