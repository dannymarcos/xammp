# ----------------------------
# Q-Learning Table (Kept as a class, but its use is within a strategy function)
# ----------------------------

import os

import pandas as pd

import logging

logger = logging.getLogger(__name__)
import traceback


class SimpleQTable:
    """Q-learning table for trading decisions with incremental updates"""

    def __init__(self, q_table_path="q_table.csv"):
        self.q_table_path = q_table_path
        self.new_entries = []
        try:
            # Use converters to ensure 'buy', 'sell', 'hold' are treated as numbers upon load
            self.q_table = pd.read_csv(
                q_table_path, converters={"buy": float, "sell": float, "hold": float}
            )
            logger.info(f"Loaded Q-table from {q_table_path}")
        except (FileNotFoundError, pd.errors.EmptyDataError):
            logger.warning(
                f"Could not load Q-table from {q_table_path} or it was empty. Initializing empty table."
            )
            self.q_table = pd.DataFrame(columns=["state", "buy", "sell", "hold"])
            # Ensure the directory exists before writing
            os.makedirs(os.path.dirname(self.q_table_path) or ".", exist_ok=True)
            self.q_table.to_csv(q_table_path, index=False)  # Create empty file
            logger.info(f"Created new Q-table at {q_table_path}")
        except Exception as e:
            logger.error(
                f"Error loading Q-table from {q_table_path}: {str(e)}. Initializing empty table."
            )
            self.q_table = pd.DataFrame(columns=["state", "buy", "sell", "hold"])
            os.makedirs(os.path.dirname(self.q_table_path) or ".", exist_ok=True)
            self.q_table.to_csv(q_table_path, index=False)  # Create empty file

    def get_action(self, state: str) -> str:
        """Get best action for given state"""
        try:
            # Check in-memory new entries first
            for entry in self.new_entries:
                if entry["state"] == state:
                    # Ensure keys exist before using them
                    return max(["buy", "sell", "hold"], key=lambda x: entry.get(x, 0.5))

            # Check existing table
            row = self.q_table[self.q_table["state"] == state]
            if not row.empty:
                # Ensure keys exist before using them
                return max(
                    ["buy", "sell", "hold"], key=lambda x: row.iloc[0].get(x, 0.5)
                )
            else:
                # Track new states encountered
                if (
                    state not in [e["state"] for e in self.new_entries]
                    and state != "state_indicators_missing"
                ):  # Don't add placeholder states
                    logger.debug(f"New state encountered: {state}")
                    self.new_entries.append(
                        {
                            "state": state,
                            "buy": 0.5,  # Initial Q-values
                            "sell": 0.5,
                            "hold": 0.5,
                        }
                    )
                return "hold"  # Default action if state not found or new

        except Exception as e:
            logger.error(f"Error getting action for state {state}: {e}")
            return "hold"  # Fallback

    def update_q_value(self, state: str, action: str, reward: float, learning_rate=0.1):
        """Update Q-value for state-action pair"""
        # Ensure state and action are valid
        if state in ["unknown", "state_indicators_missing"] or action not in [
            "buy",
            "sell",
            "hold",
        ]:
            logger.debug(
                f"Skipping Q-value update for invalid state '{state}' or action '{action}'."
            )
            return

        # Update new entries first
        for entry in self.new_entries:
            if entry["state"] == state:
                # Ensure the action column exists in the entry
                if action in entry:
                    entry[action] = (1 - learning_rate) * entry[
                        action
                    ] + learning_rate * reward
                    logger.debug(
                        f"Updated Q-value for state {state}, action {action} (new entry)"
                    )
                else:
                    logger.warning(
                        f"Action '{action}' not found in new entry for state '{state}'. Cannot update."
                    )
                return

        # Then check existing table
        if state in self.q_table["state"].values:
            idx = self.q_table[self.q_table["state"] == state].index[0]
            # Ensure the action column exists in the DataFrame
            if action in self.q_table.columns:
                self.q_table.at[idx, action] = (1 - learning_rate) * self.q_table.at[
                    idx, action
                ] + learning_rate * reward
                logger.debug(
                    f"Updated Q-value for state {state}, action {action} (existing entry)"
                )
            else:
                logger.warning(
                    f"Action column '{action}' not found in Q-table DataFrame. Cannot update."
                )
        else:
            logger.warning(
                f"Attempted to update Q-value for state '{state}' not found in new_entries or table."
            )

    def save(self, path=None):
        """Save Q-table to file, merging new entries"""
        path = path or self.q_table_path
        try:
            # Load existing table before merging, in case it was updated by another process (less likely with singleton)
            try:
                # Use converters to ensure 'buy', 'sell', 'hold' are treated as numbers
                existing_df = pd.read_csv(
                    path, converters={"buy": float, "sell": float, "hold": float}
                )
            except (FileNotFoundError, pd.errors.EmptyDataError):
                existing_df = pd.DataFrame(columns=["state", "buy", "sell", "hold"])
            except Exception as e:
                logger.error(f"Error loading Q-table before saving: {e}")
                existing_df = pd.DataFrame(
                    columns=["state", "buy", "sell", "hold"]
                )  # Fallback

            # Ensure all necessary columns exist in both DFs before merging
            cols_to_check = ["state", "buy", "sell", "hold"]
            for col in cols_to_check:
                if col not in existing_df.columns:
                    existing_df[col] = (
                        0.5 if col != "state" else None
                    )  # Add missing columns
                if (
                    col != "state" and existing_df[col].dtype != "float64"
                ):  # Ensure numeric type
                    existing_df[col] = pd.to_numeric(
                        existing_df[col], errors="coerce"
                    ).fillna(0.5)

            # Merge new entries with existing table
            if self.new_entries:
                new_df = pd.DataFrame(self.new_entries)
                # Ensure columns match and types are float for merging
                for col in ["buy", "sell", "hold"]:
                    if col in new_df.columns:
                        new_df[col] = new_df[col].astype(float)
                    if (
                        col not in existing_df.columns
                    ):  # Should already be handled above, but double check
                        existing_df[col] = 0.5  # Add missing columns with default value

                # Concatenate and drop duplicates, keeping the latest (from new_df)
                # Use ignore_index=True and reset_index after drop_duplicates
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                self.q_table = combined_df.drop_duplicates(
                    "state", keep="last"
                ).reset_index(drop=True)

                logger.info(f"Merged {len(self.new_entries)} new Q-table entries.")
                self.new_entries = []  # Clear new entries after merging

            # Save the updated table
            # Ensure float columns are saved correctly
            self.q_table[["buy", "sell", "hold"]] = self.q_table[
                ["buy", "sell", "hold"]
            ].astype(float)
            self.q_table.to_csv(path, index=False)
            logger.info(f"Q-table saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save Q-table to {path}: {str(e)}")
            traceback.print_exc()
