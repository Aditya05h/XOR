import unittest
from datetime import datetime, timedelta, timezone
from app.forecasting import forecast_series, evaluate_dataset
from app.telemetry import generate_telemetry

def points(values):
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    return [dict(timestamp=(start+timedelta(days=i)).isoformat(),rack_id='R-01',tenant_id='T1',resource_type='STORAGE',utilization_pct=v,synthetic=True,safety_threshold_pct=80,workload_id='w') for i,v in enumerate(values)]

class ForecastTests(unittest.TestCase):
    def test_linear_crossing_and_flat_no_manufactured_forecast(self):
        result=forecast_series(points([50+i*.5 for i in range(60)]),60)
        self.assertAlmostEqual(result['model']['lead_time_weeks'],41/7,places=2)
        self.assertEqual(len(result['predictions']),60)
        self.assertIsNone(result['model']['forecast_confidence_score'])
        self.assertIsNone(forecast_series(points([40]*60))['model']['predicted_exhaustion_date'])
    def test_short_observation_and_scope_validation(self):
        result=forecast_series(points([30]*5))
        self.assertFalse(result['data_quality']['sufficient_history'])
        self.assertEqual(result['predictions'],[])
        data=points([30]*20); data[-1]['tenant_id']='T2'
        with self.assertRaises(ValueError): forecast_series(data)
    def test_spike_recovery_and_sustained_shift(self):
        values=[40+i*.1 for i in range(100)]
        values[70]+=20; values[71]+=20
        report=forecast_series(points(values))
        self.assertTrue(report['history'][70]['is_transient_spike'])
        self.assertFalse(report['history'][75]['is_transient_spike'])
        shifted=[40+i*.1+(10 if i>=70 else 0) for i in range(120)]
        self.assertTrue(forecast_series(points(shifted))['model']['regime_change_detected'])
    def test_evaluator_measures_holdout_and_counts(self):
        source=generate_telemetry()
        # Exercise both actual exhaustion and a negative case without making
        # this test repeat a full 72-series backtest.
        source['points']=[p for p in source['points'] if p['rack_id'] in ('R-01','R-04') and p['resource_type']=='STORAGE']
        metrics=evaluate_dataset(source)
        self.assertEqual(metrics['series_count'],2)
        self.assertEqual(metrics['held_out_predictions'],2*5*28)
        self.assertGreaterEqual(metrics['mae_utilization_pct'],0)
        self.assertGreater(metrics['negative_case_count'],0)
        self.assertEqual(metrics['exhaustion_event_count'],1)
        self.assertGreater(metrics['detected_exhaustion_events'],0)

if __name__=='__main__': unittest.main()
