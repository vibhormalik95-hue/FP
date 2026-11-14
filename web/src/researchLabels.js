// Display labels from the observed application status, not research assumptions.
// Unknown modes remain unknown. These labels do not change any scoring behavior.
export function describeResearchMode(status) {
  const data = status?.data_mode === 'fixture' ? 'Authored fixture'
    : status?.data_mode === 'processed dataset' ? 'Dataset mode' : 'Data not verified';
  const scorer = status?.model_mode === 'deterministic diagnostic scorer' ? 'Diagnostic scorer'
    : status?.model_mode === 'trained model' ? 'Trained scorer' : 'Scorer not verified';
  return {data, scorer};
}
