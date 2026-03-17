INTENT_CATALOG = {

    "check service health": [
        "systemd.status:observer-api.service",
        "systemd.status:brain-worker.service",
        "systemd.status:observer-control.service",
    ],

    "check postgres health": [
        "systemd.status:postgresql.service"
    ],

    "check nginx health": [
        "systemd.status:nginx.service"
    ],

    "check observer api": [
        "systemd.status:observer-api.service"
    ],

    "check brain worker": [
        "systemd.status:brain-worker.service"
    ],

    "check control api": [
        "systemd.status:observer-control.service"
    ],

    "restart brain-worker.service": [
        "systemd.restart:brain-worker.service"
    ],

    "restart observer-api.service": [
        "systemd.restart:observer-api.service"
    ],

    "restart nginx.service": [
        "systemd.restart:nginx.service"
    ],

    "restart observer-bridge.service": [
        "systemd.restart:observer-bridge.service"
    ],

    "restart memory-api.service": [
        "systemd.restart:memory-api.service"
    ],

    "inspect project state": [
        "fs.read:/root/observer/PROJECT_STATE.md"
    ],

    "inspect observer handoff": [
        "fs.read:/root/observer/ssot/HANDOFF.md"
    ],

    "inspect postmortems": [
        "fs.read:/root/observer/POSTMORTEMS.md"
    ],

    "inspect metrics": [
        "fs.read:/root/observer/METRICS.md"
    ],

    "inspect logs": [
        "fs.read:/var/log/observer_consolidate.log"
    ],

    "inspect runtime flags": [
        "db.query:SELECT key, value FROM runtime_flags;"
    ],

}
