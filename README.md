# AV-Fuzzer
Reimplementation of AV-FUZZER: Finding Safety Violations in Autonomous Driving Systems (2020 ISSRE [Reference](https://github.com/cclinus/AV-Fuzzer))

## Requirements
```
apollo 6.0
lgsvl 2021.3
apollo_map: see maps/apollo_map, copy maps/apollo_map/SanFrancisco to /apollo/modules/map/data/SanFrancisco
lgsvl_map: SanFrancisco_correct link:https://wise.svlsimulator.com/maps/profile/12da60a7-2fc9-474d-a62a-5cc08cb97fe8
```

## LGSVL Config
```
Step1: Add map SanFrancisco_correct from Store to Library. Map link:https://wise.svlsimulator.com/maps/profile/12da60a7-2fc9-474d-a62a-5cc08cb97fe8

Step2: Add an API Only simulation.
```

## Steps:
```
Step1: Define your scenario config, like configs/config_ds_1.yaml

Step2: python main.py --config [your defined config.yaml] 
```
