# Automation examples

## Harmony Samsung IP control

`harmony_samsung_ip_control.yaml` is the tested pattern. Replace entity IDs, source name, and exact activity names. Every TV activity needs one `activity_power_on` trigger and one matching `activity_power_off` trigger.

## Shield sleep shutdown

`shield_sleep_shutdown.yaml` is optional and Shield-specific. It ends Harmony after either the TV or Shield has remained off for 20 seconds while the SHIELD activity is active. Use the Android TV Remote entity or another entity that reports hardware power reliably.

Configuration validation does not prove physical behavior. Run the acceptance procedure in [../../docs/TESTING.md](../../docs/TESTING.md).
