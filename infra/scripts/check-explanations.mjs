import assert from "node:assert/strict";

export async function verifyExplanations({ compose, request, terminal, pass, loginAs, marker, upload }) {
  const trainingCSV=await compose("run","--rm","--no-deps","api","python","-m","app.ml.synthetic");
  assert.ok(trainingCSV.includes(`,${marker}`));
  const uploaded=await terminal(await upload(trainingCSV));
  assert.equal(uploaded.status,"SUCCEEDED");
  const mutation=(path,value)=>request(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(value)});
  const patch=(path,value)=>request(path,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(value)});
  const started=await mutation("/admin/models/train",{training_dataset_id:uploaded.dataset_id});
  assert.equal(started.status,202);
  const trained=await terminal((await started.json()).job_id);
  assert.equal(trained.status,"SUCCEEDED");
  assert.equal((await mutation(`/admin/models/${trained.model_version_id}/activate`,{})).status,200);
  const fixtures=(mode)=>compose("run","--rm","--no-deps","-v",
    `${process.cwd()}/infra/scripts/check-scoring-db.py:/app/check_scoring_db.py:ro`,
    "api","python","check_scoring_db.py",mode);
  const rules=JSON.parse(await fixtures("rules"));
  pass("real training/activation and three isolated rule fixtures; demo seed unchanged");
  const payload={external_id:"explain-first",customer_ref:`${marker}explanation`,occurred_at:"2026-02-01T10:00:00Z",
    amount:"1000.00",currency:"INR",merchant_category:"electronics",country_code:"IN",channel:"WEB",device_ref:"device-new"};
  for (const [external_id,occurred_at] of [["prior-a","2026-02-01T09:59:00Z"],["prior-b","2026-02-01T09:59:30Z"]]) {
    assert.equal((await mutation("/transactions",{...payload,external_id,occurred_at,amount:"10.00",device_ref:"device-prior"})).status,201);
  }
  const scored=await mutation("/transactions",payload);
  assert.equal(scored.status,201);
  const original=await scored.json();
  const explanation=await (await request(`/transactions/${original.transaction_id}/explanation`)).json();
  assert.equal(explanation.rule_hits.length,3);
  assert.equal(explanation.model_version_id,trained.model_version_id);
  assert.equal(explanation.rule_evaluations.find(r=>r.code==="HIGH_VELOCITY").prior_count,2);
  assert.equal(Number(explanation.rule_evaluations.find(r=>r.code==="AMOUNT_OUTLIER").historical_mean),10);
  const sum=Object.values(explanation.component_contributions).reduce((value,c)=>value+Number(c.risk_points),0);
  assert.ok(Math.abs(sum-explanation.risk_score)<=0.5);
  assert.equal(explanation.supervised_attribution.available,false);
  assert.equal(explanation.supervised_attribution.reason,"NOT_RECORDED_AT_SCORING_TIME");
  pass("stored explanation exposes genuine rule hits, exact observations and reproducible component score");
  const settings=await (await request("/admin/settings")).json();
  const updatedSettings={medium_threshold:20,high_threshold:50,critical_threshold:80,alert_threshold:0,version:settings.version};
  assert.equal((await patch("/admin/settings",updatedSettings)).status,200);
  assert.equal((await patch("/admin/settings",updatedSettings)).status,409);
  for(const id of Object.values(rules)) assert.equal((await patch(`/admin/rules/${id}`,{enabled:false,version:1})).status,200);
  assert.equal((await patch(`/admin/rules/${rules.DEVICE_CHANGE}`,{enabled:true,version:1})).status,409);
  assert.equal((await patch(`/admin/rules/${rules.HIGH_VELOCITY}`,{parameters_json:{window_minutes:60,count_threshold:1},version:2})).status,422);
  const replay=await mutation("/transactions",payload);
  assert.equal(replay.status,200);
  assert.deepEqual(await replay.json(),original);
  assert.deepEqual(await (await request(`/transactions/${original.transaction_id}/explanation`)).json(),explanation);
  const next=await (await mutation("/transactions",{...payload,external_id:"explain-after-edit"})).json();
  const after=await (await request(`/transactions/${next.transaction_id}/explanation`)).json();
  assert.equal(after.settings_snapshot.version,2);
  assert.equal(Number(after.rule_signal),0);
  assert.ok(next.alert_id);
  assert.ok(after.rule_evaluations.every(r=>r.status==="DISABLED"));
  pass("versioned ADMIN edits affect new scores; replay and historical explanations remain unchanged");
  for(const role of ["analyst","risk-manager"]) {
    await loginAs(`${role}@sentinel-demo.invalid`);
    assert.equal((await request(`/transactions/${original.transaction_id}/explanation`)).status,200);
    assert.equal((await request("/admin/settings")).status,403);
    assert.equal((await patch("/admin/settings",{...updatedSettings,version:2})).status,403);
    assert.equal((await patch(`/admin/rules/${rules.DEVICE_CHANGE}`,{enabled:true,version:2})).status,403);
  }
  await loginAs("admin@sentinel-demo.invalid");
  assert.equal((await request("/admin/settings",{method:"PATCH",headers:{"Content-Type":"application/json","X-CSRF-Token":"invalid"},body:JSON.stringify({...updatedSettings,version:2})})).status,403);
  pass("real non-admin editing and invalid CSRF denied; ordinary explanation reads allowed");
  const csv={...payload,external_id:"explain-csv"};
  const job=await terminal(await upload(`${Object.keys(csv).join(",")}\n${Object.values(csv).join(",")}\n`,"SCORING"));
  assert.equal(job.status,"SUCCEEDED");
  assert.equal(job.processed_rows,1);
  const listed=await (await request("/transactions?search=explain-csv")).json();
  const csvExplanation=await (await request(`/transactions/${listed.items[0].id}/explanation`)).json();
  assert.equal(csvExplanation.settings_snapshot.version,2);
  assert.equal(Number(csvExplanation.rule_signal),0);
  pass("real SCORING CSV shares updated settings and persisted explanation evidence");
  await fixtures("isolation");
  await loginAs("analyst@sentinel-demo.invalid");
  assert.equal((await request(`/transactions/${original.transaction_id}/explanation`)).status,404);
  await loginAs("admin@sentinel-demo.invalid");
  pass("foreign organization cannot read explanation evidence");
}
