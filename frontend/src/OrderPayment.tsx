import { useState } from "react";
import { Alert, Button, Divider, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import { useQueryClient } from "@tanstack/react-query";
import { date, money, post } from "./api";
import type { Order, OrderCollection } from "./types";

export function OrderPaymentSummary({ collection }: { collection: OrderCollection }) {
  return <Paper variant="outlined" sx={{ p: 2 }}>
    <Typography fontWeight={700}>Payment collected · {collection.payment_method.toUpperCase()}</Typography>
    {collection.payments.map(part => <Typography key={part.method}>{part.method.toUpperCase()}: {money(part.amount)}</Typography>)}
    {collection.amount_tendered !== null && <><Divider sx={{ my: 1 }} /><Typography>Actual cash received: {money(collection.amount_tendered)}</Typography><Typography fontWeight={700}>Change returned: {money(collection.change_due)}</Typography></>}
    {collection.collected_at && <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Recorded by {collection.collected_by} · {date(collection.collected_at)}</Typography>}
  </Paper>;
}

export default function OrderPaymentPanel({ order }: { order: Order }) {
  const qc = useQueryClient();
  const [method, setMethod] = useState("cash");
  const [parts, setParts] = useState<Record<string, string>>({ cash: "", upi: "", card: "" });
  const [cash, setCash] = useState("");
  const [review, setReview] = useState<{ quote: OrderCollection; payload: Record<string, unknown> } | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  function invalidate() { setReview(null); setError(""); }
  if (order.payment_collection) return <OrderPaymentSummary collection={order.payment_collection} />;
  if (order.payment_status === "paid") return <Alert severity="info">Payment was recorded previously. Method, cash tender and change details are unavailable for this older collection.</Alert>;
  if (!["ready", "dispatched"].includes(order.status)) return null;
  async function reviewPayment() {
    setBusy(true); setError("");
    const payload = {
      payment_method: method,
      ...(method === "split" ? { payments: Object.entries(parts).filter(([, value]) => value.trim()).map(([part, value]) => ({ method: part, amount: value })) } : {}),
      ...(method === "cash" && cash.trim() ? { amount_tendered: cash } : {}),
    };
    try { setReview({ quote: await post<OrderCollection>(`/orders/${order.id}/payment/preview`, payload), payload }); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }
  async function confirmPayment() {
    if (!review) return;
    setBusy(true); setError("");
    try {
      await post(`/orders/${order.id}/payment`, { ...review.payload, expected_total: review.quote.total });
      await qc.invalidateQueries();
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }
  return <Paper variant="outlined" sx={{ p: 2 }}><Stack spacing={2}>
    <Typography variant="subtitle1" fontWeight={700}>Record payment collection · {money(order.total)}</Typography>
    <TextField select label="Payment method" value={method} disabled={busy} onChange={e => { setMethod(e.target.value); invalidate(); }}>
      {["cash", "upi", "card", "split"].map(value => <MenuItem key={value} value={value}>{value.toUpperCase()}</MenuItem>)}
    </TextField>
    {method === "split" && <><Typography variant="body2">Enter each payment portion. Leave unused methods empty.</Typography><Stack direction={{ xs: "column", sm: "row" }} gap={2}>
      {Object.entries(parts).map(([part, value]) => <TextField key={part} fullWidth type="number" label={`${part.toUpperCase()} portion`} value={value} disabled={busy} inputProps={{ min: 0.01, step: .01 }} onChange={e => { setParts({ ...parts, [part]: e.target.value }); invalidate(); }} />)}
    </Stack></>}
    {method === "cash" && <TextField type="number" label="Actual cash received" value={cash} disabled={busy} inputProps={{ min: 0, step: .01 }} helperText="Enter the notes received before giving change." onChange={e => { setCash(e.target.value); invalidate(); }} />}
    {error && <Alert severity="error">{error}</Alert>}
    {review && <><OrderPaymentSummary collection={review.quote} /><Alert severity="warning">Confirm only after receiving every listed payment and returning any change.</Alert></>}
    <Button variant="contained" disabled={busy} onClick={() => void (review ? confirmPayment() : reviewPayment())}>{busy ? "Please wait..." : review ? "Confirm collection" : "Review payment & change"}</Button>
  </Stack></Paper>;
}
