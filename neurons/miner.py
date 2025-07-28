import typing

import bittensor as bt
from synth.base.miner import BaseMinerNeuron
from synth.miner.simulations import generate_simulations
from synth.protocol import Simulation, SimulationInput


class Tracker:

    def tick(self, body: SimulationInput):
        pass


class UserModel(Tracker):

    def tick(self, body: SimulationInput):
        return generate_simulations(
            asset=body.asset,
            start_time=body.start_time,
            time_increment=body.time_increment,
            time_length=body.time_length,
            num_simulations=body.num_simulations,
            # sigma=self.config.simulation.sigma,  # Standard deviation of the simulated price path
        )


class Miner(BaseMinerNeuron):

    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)

        self.tracker = UserModel()

    async def forward_miner(self, synapse: Simulation) -> Simulation:
        simulation_input = synapse.simulation_input
        bt.logging.info(
            f"Received prediction request from: {synapse.dendrite.hotkey} for timestamp: {simulation_input.start_time}"
        )

        synapse.simulation_output = self.tracker.tick(simulation_input)

        return synapse

    async def blacklist(self, synapse: Simulation) -> typing.Tuple[bool, str]:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            return True, "Missing dendrite or hotkey"

        # HACK: Only allow Enzo's registered validator
        # TODO: Use blacklist exemptions instead (discovered after)
        if synapse.dendrite.hotkey != "5Dz6WvbgM749zdv9pk6RPFcgJPv7fB7vSNnR1AJ518wtkKcs":
            bt.logging.warning(f"Received a request from another validator: {synapse.dendrite.hotkey}")
            return True, "not my own validator"

        # HACK: Remove most of the blacklist logic
        return False, "Hotkey recognized!"

    async def priority(self, synapse: Simulation) -> float: return 0.0  # HACK: Don't care for now
    def save_state(self): pass
    def load_state(self): pass
    def set_weights(self): pass
    async def forward_validator(self): pass


if __name__ == "__main__":
    Miner().run()
