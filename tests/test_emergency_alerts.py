from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import jobs.t0_morning_digest as morning_digest
import modules.emergency_intake as emergency_intake
import modules.incident_cluster as incident_cluster
import modules.pa_alerter as pa_alerter
import sansadx_backend.db as dbmod


def _setup_incident_cluster_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    dbmod.Base.metadata.create_all(bind=engine, tables=[dbmod.IncidentCluster.__table__])
    monkeypatch.setattr(dbmod, "SessionLocal", testing_session)
    monkeypatch.setattr(dbmod, "engine", engine)
    return testing_session


def test_upsert_cluster_counts_only_unique_senders_and_non_forward_reports(monkeypatch):
    session_factory = _setup_incident_cluster_db(monkeypatch)
    config = {
        "t1_count": 3,
        "t1_window_minutes": 10,
        "t2_count": 8,
        "t2_window_minutes": 15,
        "similarity_dedup_threshold": 0.82,
    }

    cluster_id, old_level, new_level = incident_cluster.upsert_cluster(
        tenant_id=1,
        case_id=1,
        sender_phone="919111111111",
        message_text="Fire in the market near the bus stand",
        assembly="Belagavi",
        ward=None,
        hazard_type="fire",
        config=config,
    )
    assert old_level == "t0"
    assert new_level == "t0"

    incident_cluster.upsert_cluster(
        tenant_id=1,
        case_id=2,
        sender_phone="919111111111",
        message_text="Smoke is spreading near the market, please help",
        assembly="Belagavi",
        ward=None,
        hazard_type="fire",
        config=config,
    )
    incident_cluster.upsert_cluster(
        tenant_id=1,
        case_id=3,
        sender_phone="919222222222",
        message_text="Fire in the market near the bus stand",
        assembly="Belagavi",
        ward=None,
        hazard_type="fire",
        config=config,
    )
    incident_cluster.upsert_cluster(
        tenant_id=1,
        case_id=4,
        sender_phone="919333333333",
        message_text="Big flames visible beside the bus depot",
        assembly="Belagavi",
        ward=None,
        hazard_type="fire",
        config=config,
    )

    with session_factory() as db:
        cluster = db.query(dbmod.IncidentCluster).filter(dbmod.IncidentCluster.id == cluster_id).first()
        assert cluster is not None
        assert cluster.unique_sender_count == 2
        assert len(cluster.sender_events) == 2
        assert cluster.raw_case_ids == [1, 2, 3, 4]


def test_evaluate_alert_level_uses_separate_time_windows():
    now = datetime.utcnow()
    cluster = SimpleNamespace(
        id=99,
        alert_level="t0",
        unique_sender_count=3,
        sender_events=[
            {"phone": "1", "ts": (now - timedelta(minutes=14)).isoformat()},
            {"phone": "2", "ts": (now - timedelta(minutes=13)).isoformat()},
            {"phone": "3", "ts": (now - timedelta(minutes=12)).isoformat()},
        ],
        window_start=now - timedelta(minutes=14),
        created_at=now - timedelta(minutes=14),
        updated_at=now - timedelta(minutes=12),
    )
    config = {
        "t1_count": 3,
        "t1_window_minutes": 10,
        "t2_count": 4,
        "t2_window_minutes": 15,
    }

    assert incident_cluster._evaluate_alert_level(cluster, config) == "t0"

    cluster.sender_events.append({"phone": "4", "ts": (now - timedelta(minutes=2)).isoformat()})
    assert incident_cluster._evaluate_alert_level(cluster, config) == "t2"


def test_get_pending_escalation_clusters_includes_t3(monkeypatch):
    session_factory = _setup_incident_cluster_db(monkeypatch)
    now = datetime.utcnow()
    with session_factory() as db:
        db.add(
            dbmod.IncidentCluster(
                tenant_id=1,
                hazard_type="fire",
                assembly="Belagavi",
                ward=None,
                window_start=now - timedelta(minutes=20),
                unique_sender_count=8,
                raw_case_ids=[1],
                fingerprint_hashes=["fire in market"],
                sender_events=[{"phone": "919111111111", "ts": (now - timedelta(minutes=20)).isoformat()}],
                alert_level="t3",
                alert_acknowledged=False,
                last_alert_at=now - timedelta(minutes=10),
                call_attempt_count=2,
                created_at=now - timedelta(minutes=20),
                updated_at=now - timedelta(minutes=10),
            )
        )
        db.commit()

    clusters = incident_cluster.get_pending_escalation_clusters()
    assert [cluster.alert_level for cluster in clusters] == ["t3"]


def test_dispatch_t3_marks_cluster_unacknowledged_after_max_attempts(monkeypatch):
    session_factory = _setup_incident_cluster_db(monkeypatch)
    now = datetime.utcnow()
    with session_factory() as db:
        cluster = dbmod.IncidentCluster(
            tenant_id=1,
            hazard_type="fire",
            assembly="Belagavi",
            ward=None,
            window_start=now - timedelta(minutes=20),
            unique_sender_count=8,
            raw_case_ids=[1],
            fingerprint_hashes=["fire in market"],
            sender_events=[{"phone": "919111111111", "ts": (now - timedelta(minutes=20)).isoformat()}],
            alert_level="t3",
            alert_acknowledged=False,
            last_alert_at=now - timedelta(minutes=10),
            call_attempt_count=3,
            created_at=now - timedelta(minutes=20),
            updated_at=now - timedelta(minutes=10),
        )
        db.add(cluster)
        db.commit()
        cluster_id = cluster.id

    pa_alerter.dispatch_t3_alert(
        cluster_id,
        {"cluster_id": cluster_id, "hazard_type": "fire", "assembly": "Belagavi", "unique_sender_count": 8},
        {"pa_phone": "919111111111", "backup_pa_phone": "919222222222", "max_call_attempts": 3},
        None,
    )

    with session_factory() as db:
        updated = db.query(dbmod.IncidentCluster).filter(dbmod.IncidentCluster.id == cluster_id).first()
        assert updated.alert_level == "unacknowledged"


def test_escalate_pending_clusters_honors_tenant_specific_wait(monkeypatch):
    now = datetime.utcnow()
    clusters = [
        SimpleNamespace(id=1, tenant_id=101, last_alert_at=now - timedelta(minutes=10)),
        SimpleNamespace(id=2, tenant_id=202, last_alert_at=now - timedelta(minutes=10)),
    ]
    called = []

    monkeypatch.setattr(incident_cluster, "get_pending_escalation_clusters", lambda: clusters)
    monkeypatch.setattr(
        incident_cluster,
        "get_emergency_config",
        lambda tenant_id: {"escalation_wait_minutes": 5 if tenant_id == 101 else 30},
    )
    monkeypatch.setattr(
        incident_cluster,
        "build_alert_summary",
        lambda cluster: {"cluster_id": cluster.id, "hazard_type": "fire", "assembly": "Belagavi", "unique_sender_count": 5},
    )
    monkeypatch.setattr(dbmod, "get_tenant_phone_number_id", lambda tenant_id: "pnid")
    monkeypatch.setattr(
        pa_alerter,
        "dispatch_t3_alert",
        lambda cluster_id, summary, config, phone_number_id: called.append(cluster_id),
    )

    emergency_intake.escalate_pending_clusters()

    assert called == [1]


def test_filter_unclustered_cases_excludes_cases_already_in_clusters():
    cases = [
        {"id": 1, "raw_message": "fire in market"},
        {"id": 2, "raw_message": "single reporter case"},
    ]
    clusters = [
        {"raw_case_ids": [1, 3]},
    ]

    filtered = morning_digest._filter_unclustered_cases(cases, clusters)

    assert [case["id"] for case in filtered] == [2]
