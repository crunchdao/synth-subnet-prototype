import asyncio
from datetime import datetime, timedelta
import multiprocessing as mp

from dotenv import load_dotenv
import bittensor as bt

from synth.base.validator import BaseValidatorNeuron

from synth.simulation_input import SimulationInput
from synth.utils.helpers import (
    get_current_time,
    round_time_to_minutes,
    timeout_until,
)
from synth.utils.opening_hours import should_skip_xau
from synth.validator.forward import (
    calculate_moving_average_and_update_rewards,
    calculate_rewards_and_update_scores,
    get_available_miners_and_update_metagraph_history,
    query_available_miners_and_save_responses,
    send_weights_to_bittensor_and_update_weights_history,
)
from synth.validator.miner_data_handler import MinerDataHandler
from synth.validator.price_data_provider import PriceDataProvider
from neurons.shared import async_timeit


load_dotenv()


class Validator(BaseValidatorNeuron):

    def __init__(self, config=None):
        super(Validator, self).__init__(config=config)

        bt.logging.info("load_state()")
        self.load_state()

        self.miner_data_handler = MinerDataHandler()
        self.price_data_provider = PriceDataProvider()

        self.simulation_input_list = [
            # input data: give me prediction of BTC price for the next 1 day for every 5 min of time
            SimulationInput(
                asset="BTC",
                time_increment=300,
                time_length=86400,
                num_simulations=100,
            ),
        ]


    async def forward_validator(self):
        bt.logging.info("calling forward_validator()")
        
        current_time = get_current_time()

        return [
            asyncio.create_task(self.forward_prompt(current_time)),
            asyncio.create_task(self.forward_score(current_time)),
        ]

    @async_timeit(["current_time"])
    async def forward_prompt(self, current_time: datetime):
        simulation_input = self.simulation_input_list[0]
        start_time = current_time + timedelta(seconds=8)

        miner_uids = get_available_miners_and_update_metagraph_history(
            base_neuron=self,
            miner_data_handler=self.miner_data_handler,
            start_time=start_time,
        )

        if len(miner_uids) == 0:
            bt.logging.error("No miners available", "forward_prompt")
            return

        simulation_input.start_time = start_time.isoformat()

        await query_available_miners_and_save_responses(
            base_neuron=self,
            miner_data_handler=self.miner_data_handler,
            miner_uids=miner_uids,
            simulation_input=simulation_input,
            request_time=current_time,
        )

        # HACK: Should instead wait until the next iteration
        await asyncio.sleep(5)

    @async_timeit(["current_time"])
    async def forward_score(self, current_time: datetime):
        # HACK: Fake wait to let them process
        await asyncio.sleep(9)

        # HACK: Force fast iteration
        scored_time = current_time + timedelta(seconds=5)

        wait_time = timeout_until(scored_time)
        bt.logging.info(f"Waiting for {wait_time/60} minutes to start validating", "forward_score")
        await asyncio.sleep(wait_time)

        # NOTE: success here is true if at least ONE miner has answered
        success = calculate_rewards_and_update_scores(
            miner_data_handler=self.miner_data_handler,
            price_data_provider=self.price_data_provider,
            scored_time=scored_time,
            cutoff_days=self.config.ewma.cutoff_days,
        )

        if not success:
            return

        # NOTE: Not necessary for demo
        moving_averages_data = calculate_moving_average_and_update_rewards(
            miner_data_handler=self.miner_data_handler,
            scored_time=scored_time,
            cutoff_days=self.config.ewma.cutoff_days,
            half_life_days=self.config.ewma.half_life_days,
            softmax_beta=self.config.softmax.beta,
        )

        if len(moving_averages_data) == 0:
            return

        # NOTE: Not necessary for demo
        send_weights_to_bittensor_and_update_weights_history(
            base_neuron=self,
            moving_averages_data=moving_averages_data,
            miner_data_handler=self.miner_data_handler,
            scored_time=scored_time,
        )

        # HACK: Should instead wait until the next iteration
        await asyncio.sleep(1)

    async def forward_miner(self, _: bt.Synapse) -> bt.Synapse:
        pass


def webserve(validator: Validator):
    from aiohttp import web

    # HTML form as a multiline string
    form_html = """
    <!DOCTYPE html>
    <html>
    <body>
        <form method="post" action="/submit">
            <label for="asset">asset:</label><br>
            <input type="text" id="asset" name="asset" value="BTC"><br>

            <label for="time_increment">time_increment:</label><br>
            <input type="number" id="time_increment" name="time_increment" min="0" step="1" value="300"><br>

            <label for="time_length">time_length:</label><br>
            <input type="number" id="time_length" name="time_length" min="0" step="1" value="86400"><br>

            <label for="num_simulations">num_simulations:</label><br>
            <input type="number" id="num_simulations" name="num_simulations" min="0" step="1" value="100"><br>

            <input type="submit" value="Submit (look at console, no results is shown here and processing is slow)">
        </form>
    </body>
    </html>
    """

    # HTML response page as a multiline string
    response_html = """
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Hello, {name}!</h1>
        <p>Your form has been submitted successfully.</p>
        <a href="/">Go back</a>
    </body>
    </html>
    """

    async def handle_get(request):
        return web.Response(text=form_html, content_type='text/html')

    async def handle_post(request):
        data = await request.post()

        # HACK: Fast way to send inputs instead of using parameters
        previous_simulation_input_list = validator.simulation_input_list
        current_loop = asyncio.get_event_loop()
        try:
            validator.simulation_input_list = [
                SimulationInput(
                    asset=data.get('asset', 'BTC'),
                    time_increment=int(data.get('time_increment', 300)),
                    time_length=int(data.get('time_length', 86400)),
                    num_simulations=int(data.get('num_simulations', 100)),
                ),
            ]

            # Scary stuff!
            asyncio.set_event_loop(validator.loop)
            await validator.concurrent_forward()
        finally:
            validator.simulation_input_list = previous_simulation_input_list
            asyncio.set_event_loop(current_loop)

        response = response_html.format(name="world")
        return web.Response(text=response, content_type='text/html')

    app = web.Application()
    app.router.add_get('/', handle_get)
    app.router.add_post('/submit', handle_post)

    web.run_app(app)


# The main function parses the configuration and runs the validator.
if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    with Validator() as validator:
        webserve(validator)
