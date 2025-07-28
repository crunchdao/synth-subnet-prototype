from datetime import datetime
from synth.miner.simulations import generate_simulations
from synth.simulation_input import SimulationInput
from synth.utils.helpers import get_current_time, round_time_to_minutes
from synth.validator.response_validation import validate_responses
import json

# python synth/miner/run.py


if __name__ == "__main__":
    simulation_input = SimulationInput(
        asset="BTC",
        time_increment=300,
        time_length=600,
        num_simulations=2,
    )
    print("simulation_input", simulation_input.json())

    current_time = get_current_time()
    start_time = round_time_to_minutes(current_time, 60, 120)
    simulation_input.start_time = start_time.isoformat()

    print("start_time", simulation_input.start_time)
    prediction = generate_simulations(
        simulation_input.asset,
        start_time=simulation_input.start_time,
        time_increment=simulation_input.time_increment,
        time_length=simulation_input.time_length,
        num_simulations=simulation_input.num_simulations,
    )
    print("prediction", json.dumps(prediction, indent=2))

    format_validation = validate_responses(
        prediction,
        simulation_input,
        datetime.fromisoformat(simulation_input.start_time),
        "0",
    )
    print(format_validation)
