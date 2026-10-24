import assert from "node:assert/strict";

export async function verifyScoring({ compose, request, terminal, poll, ready, pass, loginAs,
  startWorkerOnly, marker, upload, inspect }) {
  const csv = await compose("run", "--rm", "--no-deps", "api", "python", "-m", "app.ml.synthetic");
  assert.ok(csv.includes(`,${marker}`));
  const trainingJob = await upload(csv);
  const training = await terminal(trainingJob);
  assert.equal(training.status, "SUCCEEDED");
  const trainResponse = await request("/admin/models/train", { method:"POST",
    headers:{"Content-Type":"application/json"}, body:JSON.stringify({training_dataset_id:training.dataset_id}) });
  assert.equal(trainResponse.status,202);
  const candidate = await terminal((await trainResponse.json()).job_id);
  assert.equal(candidate.status,"SUCCEEDED");
  assert.equal((await request(`/admin/models/${candidate.model_version_id}/activate`, {method:"POST",
    headers:{"Content-Type":"application/json"},body:"{}"})).status,200);
  pass("real synthetic TRAINING upload, Celery training and explicit model activation");
  const check = (...args) => compose("run","--rm","--no-deps","-v",
    `${process.cwd()}/infra/scripts/check-scoring-db.py:/app/check_scoring_db.py:ro`,
    "api","python","check_scoring_db.py",...args);
  await check("threshold");
  const payload = { external_id:"scoring-direct",customer_ref:`${marker}private`,
    occurred_at:"2026-02-01T02:00:00Z",amount:"5000.00",currency:"INR",merchant_category:"electronics",
    country_code:"IN",channel:"WEB",device_ref:"fictional-device" };
  const submit = (value=payload, extra={}) => request("/transactions", {method:"POST",
    headers:{"Content-Type":"application/json",...extra},body:JSON.stringify(value)});
  const first = await submit();
  assert.equal(first.status,201);
  const result=await first.json();
  assert.equal(result.model_version_id,candidate.model_version_id);
  assert.ok(result.risk_score>=0 && result.risk_score<=100 && result.alert_id);
  const detail=await (await request(`/transactions/${result.transaction_id}`)).json();
  assert.equal(detail.score.explanation_status,"PARTIAL");
  assert.equal(Number(detail.score.rule_signal),0);
  const replay=await submit({...payload,amount:5000});
  assert.equal(replay.status,200);
  assert.deepEqual(await replay.json(),result);
  assert.equal((await submit({...payload,amount:"5001"})).status,409);
  assert.equal((await submit(payload,{"X-CSRF-Token":"invalid"})).status,403);
  pass("direct 201, stored components, identical 200, conflicting 409 and forged CSRF denial");
  const concurrent=await Promise.all(Array.from({length:4},()=>submit({...payload,external_id:"scoring-concurrent"})));
  assert.deepEqual(concurrent.map(r=>r.status).sort(),[200,200,200,201]);
  const bodies=await Promise.all(concurrent.map(r=>r.json()));
  assert.ok(bodies.every(b=>b.transaction_id===bodies[0].transaction_id && b.alert_id===bodies[0].alert_id));
  for (const role of ["analyst","risk-manager"]) {
    await loginAs(`${role}@sentinel-demo.invalid`);
    assert.equal((await submit()).status,200);
  }
  await loginAs("admin@sentinel-demo.invalid");
  pass("concurrent HTTP duplicate requests create one result; all three roles can submit");
  const fields=[...Object.keys(payload),"fraud_label"];
  const scoringCSV=rows=>`${fields.join(",")}\n${rows.map(row=>fields.map(key=>({...payload,fraud_label:"0",...row})[key]).join(",")).join("\n")}\n`;
  const partial=await upload(scoringCSV([{external_id:"csv-a"},{external_id:"csv-a"},
    {external_id:"csv-a",amount:"5001"},{external_id:"csv-invalid",amount:"NaN"},
    {external_id:"csv-b",fraud_label:"1"}]),"SCORING");
  const partialResult=await terminal(partial);
  assert.equal(partialResult.status,"SUCCEEDED");
  assert.equal(partialResult.total_rows,5);
  assert.equal(partialResult.processed_rows,3);
  assert.equal(partialResult.failed_rows,2);
  assert.equal(partialResult.completed_with_row_errors,true);
  assert.equal(partialResult.progress_phase,"SCORING");
  await inspect(partial,"redeliver");
  await new Promise(resolve=>setTimeout(resolve,3000));
  assert.equal((await (await request(`/jobs/${partial}`)).json()).attempt_count,1);
  pass("real CSV partial success, exact counters, separate labels and duplicate Celery delivery");
  await compose("stop","worker");
  const retry=await upload(scoringCSV([{external_id:"csv-storage-retry"}]),"SCORING");
  await compose("stop","object-storage");
  await startWorkerOnly();
  const unavailable=await poll(`/jobs/${retry}`,j=>j.error_code==="STORAGE_UNAVAILABLE");
  assert.equal(unavailable.processed_rows,0);
  assert.equal(unavailable.status,"QUEUED");
  assert.equal((await request("/health/ready")).status,503);
  await compose("start","object-storage");
  await ready();
  const recovered=await terminal(retry);
  assert.equal(recovered.status,"SUCCEEDED");
  assert.equal(recovered.processed_rows,1);
  assert.ok(recovered.attempt_count>=2 && recovered.attempt_count<=3);
  pass("real scoring storage outage refuses progress and recovers with one row");
  const count=800;
  const crash=await upload(scoringCSV(Array.from({length:count},(_,i)=>({external_id:`crash-${i}`}))),"SCORING");
  const progressing=await poll(`/jobs/${crash}`,j=>j.status==="PROCESSING" && j.processed_rows>0 && j.processed_rows<count);
  await compose("kill","-s","SIGKILL","worker");
  const stopped=await (await request(`/jobs/${crash}`)).json();
  assert.ok(stopped.processed_rows>=progressing.processed_rows && stopped.processed_rows<count);
  await startWorkerOnly();
  const resumed=await terminal(crash);
  assert.equal(resumed.status,"SUCCEEDED");
  assert.equal(resumed.processed_rows,count);
  assert.equal(resumed.failed_rows,0);
  assert.ok(resumed.attempt_count>=2 && resumed.attempt_count<=3);
  pass("SIGKILL during real CSV scoring resumes durable progress without double counting");
  const totals=JSON.parse(await check("verify",String(count+5),String(count+3)));
  console.log(`Observed synthetic reconciliation: ${JSON.stringify(totals)}`);
  pass("transaction, score, alert, label and audit counts reconcile; every persisted score reproduces");
  await check("isolation");
  await loginAs("analyst@sentinel-demo.invalid");
  assert.equal((await request(`/transactions/${result.transaction_id}`)).status,404);
  assert.deepEqual((await (await request("/transactions")).json()).items,[]);
  const absent=await submit();
  assert.equal(absent.status,409);
  assert.equal((await absent.json()).error.code,"ACTIVE_MODEL_REQUIRED");
  await loginAs("admin@sentinel-demo.invalid");
  await check("tamper");
  assert.equal((await submit({...payload,external_id:"corrupt-refused"})).status,409);
  assert.equal((await submit()).status,200);
  await check("verify",String(count+5),String(count+3));
  pass("foreign organization denied, missing model refused, corrupted active artifact rolls back and replay survives");
}
