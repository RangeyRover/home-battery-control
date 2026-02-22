# System Requirements Design: Battery State Machine (MILP Optmizer)

## 1. Architectural Shift: From Greedy Rules to Dynamic Programming Optimization
The user has mandated a full architectural pivot. The current `fsm/default.py` relies on a greedy, point-in-time rule cascade (e.g., "Charge right now if the price is cheap"). This approach suffers from toxic edge cases—specifically, "Negative Export Traps" where the battery fills up too early and the house is forced to pay the grid to dump excess solar later in the day.

We are adopting a **Dynamic Programming (DP) Tree Search** optimization engine based on the Ironbar algorithm. This means the FSM will no longer evaluate *atomic rules in isolation*. Instead, it will compress the 24-hour mathematical matrix of predicted PV, Load, and Prices into uniform blocks, and use a recursive, memoized tree search to find the mathematically perfect 5-minute charge/discharge schedule to minimize the total daily bill.

## 2. Core Operational Flow
1. **Data Ingestion (Every 5 Minutes):** The Coordinator passes the `FSMContext` (Current SoC, 24h Price Forecast, 24h PV Forecast, 24h Load Forecast).
2. **Matrix Construction:** The optimizer constructs an array of 288 time steps (24 hours * 12 slots/hr).
3. **Period Compression:** To save computation time, adjacent 5-minute ticks with the same electricity price and same solar/load balance direction are compressed into continuous "blocks".
4. **Recursive DP Solve (Cost Minimization):** The algorithm explores all safe battery capacity changes between blocks. It recursively calculates the cheapest path to the end of the 24-hour horizon, caching results (`@lru_cache`) to avoid redundant branch execution.
5. **Action Execution:** The FSM takes only the *very first result* from the resolved DP tree path (the absolute `now`) and outputs the corresponding `state` and `limit_kw` to command the physical battery. 5 minutes later, the entire tree is rebuilt and re-solved from the new starting SoC.

## 3. Mathematical Formulation (Derived from Ironbar DP Algorithm)

### Variables (Per Compressed Block)
- `initial_charge`: The starting SoC of the battery for the block.
- `target_charge_range`: An array of candidate ending SoC percentages the solver is allowed to explore.
- `balance`: The net load of the house (Load - PV) assumed constant for the block.

### Execution Constraints
1. **Battery Physics:** `target_charge_range` is strictly bounded between 0% and 100%.
2. **Inverter Limits:** The delta between `initial_charge` and target SoC is constrained by `Max_Charge_kW` and `Max_Discharge_kW` multiplied by the block's physical duration in hours.
3. **Period Compression:** To prevent exponential explosion of the recursive tree search, periods of *constant electricity price* and *unidirectional energy flow* (always charging or always discharging) are compressed into single blocks.

### The Objective Function (What the solver minimizes)
The recursive `@lru_cache` tree search continuously minimizes:
`Cost = (Total_Balance_kWh * Applicable_Price_c)` 
returning the cheapest available path constraint recursively from the horizon to the current tick.

## 4. Implementation Challenges & Requirements

### 1. Library Selection
To perform this processing, we rely entirely on **native Python**, heavily leveraging `numpy` and `pandas` for time-series array manipulation.
**Crucially, this approach requires NO external optimization engines** (like GLPK, CBC, or CPLEX). Because it is mathematically self-contained, it is significantly safer to deploy within the Home Assistant container without fearing broken C++ dependencies.

### 2. The Negative Export Solution
By defining a mathematically rigid constraint block, the "Negative Export Trap" solves itself natively. 
If `ExportPrice` in the future is `-50c` (meaning exporting solar produces a massive financial penalty), the DP tree will discover that arriving at that future tick with an empty battery produces the mathematically lowest cost (as the empty battery provides space to absorb the toxic solar). 
Because the algorithm walks backwards recursively, it passes this cost constraint back to `tick 0`, forcing the battery to `IDLE` (or discharge) immediately to prevent overcharging.

### 3. Execution Limitations
While it does not rely on external C++ mathematical solvers, a recursive DP tree search is still CPU intensive. To prevent blocking the Home Assistant event loop, this optimization **must** be executed in an asynchronous thread (`hass.async_add_executor_job`).

### A. The Challenge of Negative Feed-in Tariffs (The "Negative Export" Edge Case)
As highlighted by the user: *what happens when the battery is full (95%), the sun is shining (excess PV), but the export price is negative (meaning you have to pay the grid to take your solar power)?*

Currently, the fallback FSM rules hit `IDLE` (Rule 7) when the battery is full. In a normal environment, this means the inverter naturally exports the excess PV to the grid. 
However, **if the export price is negative, this fallback behavior financially penalizes the user**. The system needs an explicit `FORCE_CURTAIL` or `INCREASE_LOAD` state to stop the export, or it needs the foresight to stop charging *earlier* in the day (so the battery has room to absorb the excess PV exactly when the export price goes negative).

### B. Rule-Based vs Dynamic Programming (DP)
Here is the fundamental difference in architectural approaches:

**1. The Current Approach: Deterministic Rule-Based FSM**
- **How it works:** Look at the current moment in time. Run down a checklist of `IF/THEN` statements. Make the best immediate choice.
- **Pros:** Fast to compute, easy to debug (you can trace exactly which rule fired), predictable, easy to program in Python.
- **Cons:** Very poor at global optimization. It is "greedy." It might charge the battery fully during a 10c/kWh window at 10 AM, only to discover there is a -5c/kWh window at 1 PM where it *should* have been charging and getting paid. It can't "unwind" its past decisions.

**2. The Optimization Approach: Dynamic Programming (DP)**
- **How it works:** You define an objective function (e.g., `Minimize: Total Daily Cost = Import Cost - Export Revenue`). You define all the physical constraints (Maximum Battery Capacity, Max Charge Rate). You feed it the entire 24-hour forecast (Prices, PV, Load). The solver compresses the forecast into mathematical blocks and mathematically calculates the absolute perfect 24-hour schedule to achieve the lowest possible bill by exploring all safe configuration states in a `@lru_cache` accelerated tree search.
- **Pros:** It guarantees the absolute optimal financial outcome. It natively handles complex interactions (like leaving the battery exactly 20% empty in the morning so it can absorb excess PV during a negative export window at 1 PM). It requires no external solver libraries.
- **Cons:** Computationally heavy. Requires CPU time to build and traverse the cache tree.

### C. The Control Strategy (Proposed Path Forward)
We will embed the `PeriodOptimizer` tree search mathematically into a new `DpBatteryStateMachine` that extends the FSM class. The Home Assistant `coordinator.py` will pass its prediction arrays natively to this model, allowing it to govern the physical battery based on its mathematical path resolution.
