document.addEventListener("DOMContentLoaded", () => {
	const container = document.getElementById("strategy-bot");
	const strategyNameInput = document.getElementById("strategy-name");
	const strategyDescriptionInput = document.getElementById(
		"strategy-description"
	);
	const saveStrategyButton = document.getElementById("save-strategy");
	const deleteStrategyButton = document.getElementById("delete-strategy");
	const strategyListSelect = container.querySelector(".strategy-list");

	let selectedStrategyId = null;

	// Function to fetch all strategies
	const fetchStrategies = async () => {
		try {
			const response = await fetch("/strategies");
			const data = await response.json();
			console.log(data);
			if (data.strategies) {
				strategyListSelect.innerHTML = "";
				data.strategies.forEach(strategy => {
					const option = document.createElement("option");
					option.value = strategy.id;
					option.textContent = strategy.name;
					strategyListSelect.appendChild(option);
				});
				if (data.strategies.length === 0) {
					const option = document.createElement("option");
					option.value = "";
					option.textContent = "No strategies saved";
					strategyListSelect.appendChild(option);
					deleteStrategyButton.disabled = true;
				} else {
					deleteStrategyButton.disabled = false;
				}
			}
		} catch (error) {
			console.error("Error fetching strategies:", error);
		}
	};

	// Function to save a strategy
	const saveStrategy = async () => {
		const name = strategyNameInput.value;
		const text = strategyDescriptionInput.value;

		if (!name || !text) {
			alert("Please enter a strategy name and description.");
			return;
		}
		saveStrategyButton.disabled = true;
		saveStrategyButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...';

		try {
			const response = await fetch("/strategies", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({ name: name, text: text }),
			});

			const data = await response.json();

			if (data.message === "Strategy saved successfully") {
				strategyNameInput.value = "";
				strategyDescriptionInput.value = "";
				fetchStrategies();
			} else {
				console.error("Error saving strategy:", data.message);
			}
		} catch (error) {
			console.error("Error saving strategy:", error);
		} finally {
			saveStrategyButton.disabled = false;
			saveStrategyButton.innerHTML = '<i class="bi bi-save"></i> Save Strategy';
		}
	};

	// Function to delete a strategy
	const deleteStrategy = async () => {
		if (!selectedStrategyId) {
			alert("Please select a strategy to delete.");
			return;
		}
		deleteStrategyButton.disabled = true;
		deleteStrategyButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Deleting...';

		try {
			const response = await fetch("/strategies", {
				method: "DELETE",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({ id: selectedStrategyId }),
			});

			const data = await response.json();

			if (data.message === "Strategy deleted successfully") {
				fetchStrategies();
				selectedStrategyId = null;
				deleteStrategyButton.disabled = true;
			} else {
				console.error("Error deleting strategy:", data.message);
			}
		} catch (error) {
			console.error("Error deleting strategy:", error);
		} finally {
			deleteStrategyButton.disabled = false;
			deleteStrategyButton.innerHTML = '<i class="bi bi-trash"></i> Delete Selected';
		}
	};

	// Event listeners
	saveStrategyButton.addEventListener("click", saveStrategy);
	deleteStrategyButton.addEventListener("click", deleteStrategy);

	strategyListSelect.addEventListener("change", event => {
		selectedStrategyId = event.target.value;
		deleteStrategyButton.disabled = !selectedStrategyId;
	});

	// Initial fetch of strategies
	fetchStrategies();
});
