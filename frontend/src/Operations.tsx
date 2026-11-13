import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Alert,
  Autocomplete,
  Badge,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import DashboardOutlined from "@mui/icons-material/DashboardOutlined";
import PointOfSaleOutlined from "@mui/icons-material/PointOfSaleOutlined";
import Inventory2Outlined from "@mui/icons-material/Inventory2Outlined";
import ReceiptLongOutlined from "@mui/icons-material/ReceiptLongOutlined";
import SwapHorizOutlined from "@mui/icons-material/SwapHorizOutlined";
import PeopleOutline from "@mui/icons-material/PeopleOutline";
import StorefrontOutlined from "@mui/icons-material/StorefrontOutlined";
import Add from "@mui/icons-material/Add";
import Close from "@mui/icons-material/Close";
import DownloadOutlined from "@mui/icons-material/DownloadOutlined";
import UploadFileOutlined from "@mui/icons-material/UploadFileOutlined";
import SearchOutlined from "@mui/icons-material/SearchOutlined";
import QrCodeScannerOutlined from "@mui/icons-material/QrCodeScannerOutlined";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, key, money, post, quantity, date, amount, upload } from "./api";
import { useApp } from "./context";
import type {
  Branch,
  Dashboard,
  Order,
  Product,
  Sale,
  Stock,
  User,
} from "./types";
import { Loading } from "./App";
import { useConfirmDialog } from "./ConfirmDialog";
import DeliveryManagement from "./DeliveryManagement";
import OrderPaymentPanel, { OrderPaymentSummary } from "./OrderPayment";

type RecordData = Record<string, unknown>;
type Column<T> = { label: string; value: (row: T) => React.ReactNode };
export function DataTable<T>({
  rows,
  columns,
}: {
  rows: T[];
  columns: Column<T>[];
}) {
  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            {columns.map((c) => (
              <TableCell key={c.label}>{c.label}</TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow key={i} hover>
              {columns.map((c) => (
                <TableCell key={c.label}>{c.value(r)}</TableCell>
              ))}
            </TableRow>
          ))}
          {!rows.length && (
            <TableRow>
              <TableCell
                colSpan={columns.length}
                sx={{ py: 5, textAlign: "center", color: "text.secondary" }}
              >
                No records yet.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
function Status({ value }: { value: string }) {
  return (
    <Chip
      size="small"
      label={value.replaceAll("_", " ")}
      color={
        ["paid", "received", "completed", "active"].includes(value)
          ? "success"
          : value === "approval_pending"
            ? "warning"
            : value === "rejected"
              ? "error"
              : ["cancelled", "inactive"].includes(value)
                ? "default"
                : "primary"
      }
      variant="outlined"
    />
  );
}
function ProductBulkActions() {
  const { notify } = useApp(),
    qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  async function select(file: File) {
    setBusy(true);
    try {
      const result = await upload<{
        products_created: number;
        variants_created: number;
      }>("/admin/products/bulk-import", file);
      await qc.invalidateQueries();
      notify(
        `${result.products_created} products and ${result.variants_created} selling options imported.`,
      );
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Button
        href="/api/v1/admin/products/import-template"
        startIcon={<DownloadOutlined />}
      >
        Download Excel template
      </Button>
      <Button
        component="label"
        variant="outlined"
        startIcon={<UploadFileOutlined />}
        disabled={busy}
      >
        {busy ? "Importing…" : "Bulk import Excel"}
        <input
          hidden
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void select(file);
            e.target.value = "";
          }}
        />
      </Button>
    </>
  );
}
function Heading({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="workspace-heading">
      <div>
        <span className="eyebrow">CHINNU WORKSPACE</span>
        <Typography variant="h4">{title}</Typography>
        <Typography color="text.secondary" sx={{ mt: 1 }}>
          {subtitle}
        </Typography>
      </div>
      {title === "Product catalogue" ? (
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <ProductBulkActions />
          {action}
        </Stack>
      ) : title === "Branch inventory" ? (
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <Button
            href="/api/v1/inventory/barcode-sheet"
            target="_blank"
            rel="noopener noreferrer"
            variant="outlined"
          >
            Barcode labels
          </Button>
          {action}
        </Stack>
      ) : (
        action
      )}
    </div>
  );
}

export function Operations() {
  const { user } = useApp();
  const allowed = user?.workspace_pages || [];
  const path = useLocation().pathname.split("/")[2] || allowed[0] || "";
  const navigate = useNavigate();
  const branches = useQuery({
    queryKey: ["branches"],
    queryFn: () => api<Branch[]>("/branches"),
  });
  const [branch, setBranch] = useState(user?.branch_id || 0);
  const can = (permission: string) => !!user?.permissions.includes(permission);
  const admin = can("branch.switch");
  const navItems = [
    { id: "dashboard", name: "Overview", icon: <DashboardOutlined /> },
    { id: "pos", name: "Point of sale", icon: <PointOfSaleOutlined /> },
    { id: "shifts", name: "Cashier shifts", icon: <PointOfSaleOutlined /> },
    { id: "orders", name: "Online orders", icon: <ReceiptLongOutlined /> },
    { id: "deliveries", name: "Delivery management", icon: <ReceiptLongOutlined /> },
    { id: "inventory", name: "Inventory", icon: <Inventory2Outlined /> },
    { id: "counts", name: "Stock counts", icon: <Inventory2Outlined /> },
    { id: "transfers", name: "Stock transfers", icon: <SwapHorizOutlined /> },
    { id: "purchases", name: "Purchases", icon: <ReceiptLongOutlined /> },
    { id: "sales", name: "Sales & receipts", icon: <ReceiptLongOutlined /> },
    { id: "products", name: "Products", icon: <Inventory2Outlined /> },
    { id: "branches", name: "Branches", icon: <StorefrontOutlined /> },
    { id: "users", name: "People & access", icon: <PeopleOutline /> },
    { id: "customers", name: "Customers", icon: <PeopleOutline /> },
    { id: "settings", name: "Settings", icon: <ReceiptLongOutlined /> },
    { id: "audit", name: "Audit history", icon: <ReceiptLongOutlined /> },
  ];
  const adminOrder = [
    "dashboard",
    "branches",
    "users",
    "shifts",
    "products",
    "orders",
    "deliveries",
    "inventory",
    "counts",
    "transfers",
    "purchases",
    "sales",
    "customers",
    "settings",
    "audit",
  ];
  const nav = navItems
    .filter((x) => allowed.includes(x.id) && x.id !== "audit")
    .sort((a, b) =>
      user?.role === "admin"
        ? adminOrder.indexOf(a.id) - adminOrder.indexOf(b.id)
        : 0,
    );
  return (
    <div className="workspace">
      <aside className="sidebar">
        <div className="workspace-profile">
          <span className="avatar">{user?.name.charAt(0)}</span>
          <div>
            <strong>{user?.name}</strong>
            <small>{user?.role} workspace</small>
          </div>
        </div>
        <div className="sidebar-label">OPERATIONS</div>
        {nav.map((n) => (
          <Link
            to={"/workspace/" + n.id}
            key={n.id}
            className={"nav-item " + (path === n.id ? "active" : "")}
            aria-current={path === n.id ? "page" : undefined}
          >
            {n.icon}
            {n.name}
          </Link>
        ))}
        <div className="sidebar-bottom">
          <span className="connection-dot" /> Shared stock · Connected business
        </div>
      </aside>
      <main className="workspace-main">
        <div className="workspace-top">
          <div>
            <strong>
              {branch === 0
                ? "All branches"
                : branches.data?.find((b) => b.id === branch)?.name ||
                  "Branch workspace"}
            </strong>
            <span>One catalogue. Every channel.</span>
          </div>
          {admin && (
            <TextField
              select
              size="small"
              label="Branch filter"
              value={branch}
              onChange={(e) => setBranch(Number(e.target.value))}
              sx={{ minWidth: 195 }}
            >
              <MenuItem value={0}>All branches</MenuItem>
              {branches.data?.map((b) => (
                <MenuItem key={b.id} value={b.id}>
                  {b.name}
                </MenuItem>
              ))}
            </TextField>
          )}
          <Chip
            label={new Date().toLocaleDateString("en-IN", {
              day: "numeric",
              month: "short",
              year: "numeric",
            })}
            variant="outlined"
          />
        </div>
        {branches.isError && (
          <Alert severity="error">{branches.error.message}</Alert>
        )}
        {!nav.some((x) => x.id === path) ? (
          <Alert severity="warning">
            This screen is not available for your role.
          </Alert>
        ) : path === "dashboard" ? (
          <DashboardPage branch={branch} />
        ) : path === "pos" ? (
          <POS key={branch} branch={branch} />
        ) : path === "shifts" ? (
          <Shifts branch={branch} />
        ) : path === "counts" ? (
          <StockCounts branch={branch} />
        ) : path === "orders" ? (
          <BranchOrders branch={branch} />
        ) : path === "deliveries" ? (
          <DeliveryManagement branch={branch} />
        ) : path === "inventory" ? (
          <Inventory branch={branch} />
        ) : path === "transfers" ? (
          <Transfers branch={branch} branches={branches.data || []} />
        ) : path === "purchases" ? (
          <Purchases branch={branch} />
        ) : path === "sales" ? (
          <Sales branch={branch} />
        ) : path === "products" ? (
          <Products />
        ) : path === "branches" ? (
          <Branches branches={branches.data || []} />
        ) : path === "users" ? (
          <Users branches={branches.data || []} selectedBranch={branch} />
        ) : path === "customers" ? (
          <Customers />
        ) : path === "settings" ? (
          <Settings />
        ) : (
          <AuditPage />
        )}
      </main>
    </div>
  );
}

function DashboardPage({ branch }: { branch: number }) {
  const { user } = useApp();
  const all = branch === 0;
  const query = useQuery({
    queryKey: ["dashboard", all ? 0 : branch],
    queryFn: () =>
      api<Dashboard>("/dashboard" + (all ? "" : `?branch_id=${branch}`)),
    refetchInterval: 15000,
  });
  const d = query.data;
  const max = Math.max(
    1,
    ...(d?.trend.map((x) => Number(x.pos) + Number(x.online)) || []),
  );
  return (
    <>
      <Heading
        title="Business overview"
        subtitle={
          all
            ? "Sales, orders, and stock across all branches."
            : "Sales, orders, and stock for the selected branch."
        }
      />
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}
      {!d ? (
        <Loading />
      ) : (
        <>
          <div className="metric-grid">
            {[
              {
                name: "Total sales",
                value: money(d.net_sales),
                note: "POS + completed online orders (after POS refunds)",
              },
              {
                name: "In-store sales",
                value: money(d.pos_sales),
                note: `${d.sales_count} bills since the beginning; refunds deducted`,
              },
              {
                name: "Pending online orders",
                value: d.pending_orders,
                note: `${d.orders_count} online orders in total`,
              },
              {
                name: "Low-stock items",
                value: d.low_stock,
                note: "Product options at or below their restock limit, counted per branch",
              },
            ].map((m, i) => (
              <Paper
                key={m.name}
                className={"metric metric-" + i}
                variant="outlined"
              >
                <span>{m.name}</span>
                <strong>{m.value}</strong>
                <small>{m.note}</small>
              </Paper>
            ))}
          </div>
          <div className="dashboard-grid">
            <Paper variant="outlined" sx={{ p: 3 }}>
              <Stack direction="row" justifyContent="space-between">
                <div>
                  <Typography variant="h6">
                    Sales over the last 7 days
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    In-store and completed online sales · India time
                  </Typography>
                </div>
                <Stack direction="row" spacing={1}>
                  <Chip size="small" label="In-store" />
                  <Chip size="small" color="primary" label="Online" />
                </Stack>
              </Stack>
              <div className="chart">
                {d.trend.map((t) => (
                  <div className="chart-column" key={t.day}>
                    <span className="chart-value">
                      {money(Number(t.pos) + Number(t.online))}
                    </span>
                    <div className="chart-track">
                      <div
                        className="chart-pos"
                        style={{ height: `${(Number(t.pos) / max) * 160}px` }}
                      />
                      <div
                        className="chart-online"
                        style={{
                          height: `${(Number(t.online) / max) * 160}px`,
                        }}
                      />
                    </div>
                    <span>
                      {new Date(t.day + "T12:00:00").toLocaleDateString(
                        "en-IN",
                        { weekday: "short" },
                      )}
                    </span>
                  </div>
                ))}
              </div>
            </Paper>
            <Paper variant="outlined" className="priority-panel" sx={{ p: 3 }}>
              <span className="eyebrow">MAKE YOUR NEXT MOVE</span>
              <Typography variant="h5" sx={{ my: 2 }}>
                A good day starts
                <br />
                with a clear queue.
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Check new orders, keep essentials stocked, and help every
                customer finish their grocery run.
              </Typography>
              <Stack spacing={1.5}>
                {user?.role !== "inventory" && (
                  <Button
                    component={Link}
                    to="/workspace/orders"
                    variant="contained"
                  >
                    Process online orders
                  </Button>
                )}
                <Button
                  component={Link}
                  to="/workspace/inventory"
                  variant="outlined"
                >
                  Review branch inventory
                </Button>
                {["admin", "manager"].includes(user!.role) && (
                  <Button
                    href={
                      "/api/v1/reports/sales.csv" +
                      (all ? "" : `?branch_id=${branch}`)
                    }
                    startIcon={<DownloadOutlined />}
                  >
                    Download sales report
                  </Button>
                )}
              </Stack>
            </Paper>
          </div>
        </>
      )}
    </>
  );
}

function POS({ branch }: { branch: number }) {
  const [shiftAlert, setShiftAlert] = useState(false);
  const alertedShiftBranch = useRef<number | null>(null);
  type ScanResult = {
    variant_id: number;
    sku: string;
    name: string;
    label: string;
    unit: string;
    step: string;
    min_qty: string;
    max_qty: string;
    available: string;
    requires_quantity: boolean;
  };
  const { catalogue, notify, user } = useApp(),
    qc = useQueryClient();
  const confirmation = useConfirmDialog();
  const [barcode, setBarcode] = useState(""),
    [scanMessage, setScanMessage] = useState<{
      kind: "success" | "error";
      text: string;
    } | null>(null),
    [scanBusy, setScanBusy] = useState(false),
    [pendingLoose, setPendingLoose] = useState<ScanResult | null>(null),
    [looseQuantity, setLooseQuantity] = useState(""),
    [search, setSearch] = useState(""),
    [cart, setCart] = useState<{ variant_id: number; quantity: number }[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [receipt, setReceipt] = useState<Sale | null>(null),
    [paymentMethod, setPaymentMethod] = useState<
      "cash" | "card" | "upi" | "split"
    >("cash"),
    [amountTendered, setAmountTendered] = useState(""),
    [splitCash, setSplitCash] = useState(""),
    [splitCard, setSplitCard] = useState(""),
    [splitUpi, setSplitUpi] = useState(""),
    [customerMobile, setCustomerMobile] = useState(""),
    [customerName, setCustomerName] = useState("");
  const keyRef = useRef(""),
    scanRef = useRef<HTMLInputElement>(null);
  const stockQuery = useQuery({
    queryKey: ["inventory", branch],
    queryFn: () => api<Stock[]>(`/inventory?branch_id=${branch}`),
  });
  const stocks = {
    ...stockQuery,
    error: stockQuery.error ?? new Error("Inventory could not be loaded."),
  };
  const shifts = useQuery({
    queryKey: ["shifts", branch],
    queryFn: () => api<Shift[]>(`/shifts?branch_id=${branch}`),
    refetchInterval: 5000,
  });
  useEffect(() => {
    const code = barcode.trim();
    if (scanBusy || code.length < 2) return;
    const timer = window.setTimeout(() => void scan(code), 300);
    return () => window.clearTimeout(timer);
  }, [barcode, scanBusy, branch]);
  useEffect(() => {
    if (scanBusy || pendingLoose) return;
    const frame = window.requestAnimationFrame(() => scanRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [scanBusy, pendingLoose]);
  const customerLookup = useQuery({
    queryKey: ["pos-customer", customerMobile],
    queryFn: () =>
      api<{ found: boolean; name: string | null }>(
        `/pos-customers/lookup?mobile=${customerMobile}`,
      ),
    enabled: /^[6-9][0-9]{9}$/.test(customerMobile),
    retry: false,
  });
  useEffect(() => {
    if (customerLookup.data?.found)
      setCustomerName(customerLookup.data.name || "");
    else if (customerLookup.data && !customerLookup.data.found)
      setCustomerName("");
  }, [customerLookup.data, customerMobile]);
  const hasShift = shifts.data?.some(
    (s) => s.actor_id === user?.id && !s.closed_at,
  );
  useEffect(() => {
    if (!shifts.isSuccess) return;
    if (hasShift) {
      alertedShiftBranch.current = null;
      setShiftAlert(false);
    } else if (alertedShiftBranch.current !== branch) {
      alertedShiftBranch.current = branch;
      setShiftAlert(true);
    }
  }, [branch, hasShift, shifts.isSuccess]);
  const variants = catalogue.flatMap((p) =>
    p.variants.map((v) => ({ ...v, name: p.name, category: p.category })),
  );
  const results = variants.filter((v) =>
    (v.name + " " + v.sku).toLowerCase().includes(search.toLowerCase()),
  );
  const items = cart
    .map((c) => ({ ...c, v: variants.find((v) => v.id === c.variant_id)! }))
    .filter((x) => x.v);
  const total = items.reduce(
    (sum, x) => sum + amount(x.v.price, x.quantity),
    0,
  );
  useEffect(() => {
    keyRef.current = "";
  }, [JSON.stringify(cart)]);
  function add(id: number) {
    if (!hasShift) { notify("Open your cashier shift before adding products to the bill."); return; }
    const v = variants.find((x) => x.id === id)!;
    void scan(v.sku);
  }
  async function scan(value = barcode) {
    if (!hasShift) { notify("Open your cashier shift before adding products to the bill."); return; }
    const code = value.trim();
    if (!code || scanBusy) return;
    setScanBusy(true);
    setBarcode("");
    setScanMessage(null);
    try {
      const found = await api<ScanResult>(
        `/pos/scan?branch_id=${branch}&code=${encodeURIComponent(code)}`,
      );
      if (found.requires_quantity) {
        setPendingLoose(found);
        setLooseQuantity(found.min_qty);
        return;
      }
      const current =
        cart.find((x) => x.variant_id === found.variant_id)?.quantity || 0;
      const next = current
        ? Number((current + Number(found.step)).toFixed(3))
        : Number(found.min_qty);
      if (next > Math.min(Number(found.available), Number(found.max_qty)))
        throw new Error(
          `Cannot add more ${found.name}. The branch has ${quantity(found.available)} available.`,
        );
      setCart((lines) =>
        lines.some((x) => x.variant_id === found.variant_id)
          ? lines.map((x) =>
              x.variant_id === found.variant_id ? { ...x, quantity: next } : x,
            )
          : [...lines, { variant_id: found.variant_id, quantity: next }],
      );
      setSearch("");
      setScanMessage({
        kind: "success",
        text: `Added ${found.name} · ${found.label}`,
      });
    } catch (err) {
      setScanMessage({ kind: "error", text: (err as Error).message });
    } finally {
      setScanBusy(false);
    }
  }
  function looseValidation() {
    if (!pendingLoose) return "No loose item selected.";
    const entered = Number(looseQuantity),
      current =
        cart.find((x) => x.variant_id === pendingLoose.variant_id)?.quantity ||
        0,
      min = Number(pendingLoose.min_qty),
      step = Number(pendingLoose.step),
      limit = Math.min(
        Number(pendingLoose.available),
        Number(pendingLoose.max_qty),
      );
    if (!Number.isFinite(entered) || entered <= 0)
      return "Enter a valid quantity.";
    if (!current && entered < min)
      return `Minimum quantity is ${quantity(min)} ${pendingLoose.unit}.`;
    const base = current ? 0 : min;
    if (
      Math.abs((entered - base) / step - Math.round((entered - base) / step)) >
      0.000001
    )
      return `Use increments of ${quantity(step)} ${pendingLoose.unit}.`;
    if (current + entered > limit)
      return `Only ${quantity(limit - current)} ${pendingLoose.unit} more can be added.`;
    return "";
  }
  function addLoose() {
    if (!hasShift) { notify("Open your cashier shift before adding products to the bill."); return; }
    if (!pendingLoose) return;
    const validation = looseValidation();
    if (validation) return;
    const entered = Number(looseQuantity);
    setCart((lines) =>
      lines.some((x) => x.variant_id === pendingLoose.variant_id)
        ? lines.map((x) =>
            x.variant_id === pendingLoose.variant_id
              ? { ...x, quantity: Number((x.quantity + entered).toFixed(3)) }
              : x,
          )
        : [
            ...lines,
            { variant_id: pendingLoose.variant_id, quantity: entered },
          ],
    );
    setSearch("");
    setScanMessage({
      kind: "success",
      text: `Added ${quantity(entered)} ${pendingLoose.unit} of ${pendingLoose.name}`,
    });
    setPendingLoose(null);
    setLooseQuantity("");
  }
  async function complete() {
    setBusy(true);
    setError("");
    try {
      if (!keyRef.current) keyRef.current = key();
      const r = await post<{ id: number }>(
        "/sales",
        {
          branch_id: branch,
          items: cart,
          customer_mobile: customerMobile,
          customer_name: customerLookup.data?.found ? undefined : customerName,
          payment_method: paymentMethod,
          payments:
            paymentMethod === "split"
              ? [
                  { method: "cash", amount: splitCash },
                  { method: "card", amount: splitCard },
                  { method: "upi", amount: splitUpi },
                ].filter((payment) => Number(payment.amount) > 0)
              : undefined,
          amount_tendered:
            paymentMethod === "cash"
              ? amountTendered
              : undefined,
          expected_subtotal: total.toFixed(2),
        },
        keyRef.current,
      );
      const sales = await api<Sale[]>(`/sales?branch_id=${branch}`);
      setReceipt(sales.find((s) => s.id === r.id) || null);
      setCart([]);
      setAmountTendered("");
      setSplitCash("");
      setSplitCard("");
      setSplitUpi("");
      setCustomerMobile("");
      setCustomerName("");
      await qc.invalidateQueries();
      notify("Sale completed and customer saved.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function hold() {
    if (!cart.length) return;
    localStorage.setItem("grove-held-" + branch, JSON.stringify(cart));
    setCart([]);
    notify("Bill held on this device. Resume before holding another bill.");
  }
  function resume() {
    if (!hasShift) { notify("Open your cashier shift before resuming a bill."); return; }
    if (cart.length) {
      notify("Clear or finish the current bill first.");
      return;
    }
    try {
      setCart(JSON.parse(localStorage.getItem("grove-held-" + branch) || "[]"));
      localStorage.removeItem("grove-held-" + branch);
    } catch {
      notify("Held bill could not be read.");
    }
  }
  const splitTotal =
    Number(splitCash || 0) + Number(splitCard || 0) + Number(splitUpi || 0);
  const splitMethods = [splitCash, splitCard, splitUpi].filter(
    (value) => Number(value) > 0,
  ).length;
  const paymentValid =
    paymentMethod === "cash"
      ? amountTendered !== "" && Number(amountTendered) >= total
      : paymentMethod === "split"
        ? splitMethods >= 2 &&
          Math.abs(splitTotal - total) < 0.005
        : true;
  const customerValid =
    /^[6-9][0-9]{9}$/.test(customerMobile) &&
    customerName.trim().length >= 2 &&
    !customerLookup.isFetching;
  return (
    <>
      <Heading
        title="Point of sale"
        subtitle="Scan, add, and bill. Prices and stock are checked on completion."
        action={<Chip label="POS billing" color="primary" variant="outlined" />}
      />
      <Dialog open={shiftAlert} onClose={() => setShiftAlert(false)} fullWidth maxWidth="xs">
        <DialogTitle>Open your cashier shift</DialogTitle>
        <DialogContent>
          <Alert severity="warning">
            Your cashier shift is not open. Open a shift before adding products, scanning barcodes, or completing a bill.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShiftAlert(false)}>Close</Button>
          <Button component={Link} to="/workspace/shifts" variant="contained">Go to cashier shifts</Button>
        </DialogActions>
      </Dialog>
      {!hasShift && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Open your{" "}
          <Link to="/workspace/shifts">
            <strong>cashier shift</strong>
          </Link>{" "}
          before adding products or completing sales.
        </Alert>
      )}
      <div className="pos-grid">
        <div>
          <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
            <TextField
              inputRef={scanRef}
              autoFocus
              fullWidth
              label="Scan barcode or enter SKU"
              value={barcode}
              onChange={(e) => setBarcode(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void scan(barcode);
                }
              }}
              disabled={scanBusy || !hasShift}
              helperText="Scan continuously—each barcode is added automatically without pressing Enter."
              slotProps={{
                input: {
                  startAdornment: <QrCodeScannerOutlined sx={{ mr: 1 }} />,
                },
              }}
            />
            {scanMessage && (
              <Alert severity={scanMessage.kind} sx={{ mt: 1 }}>
                {scanMessage.text}
              </Alert>
            )}
          </Paper>
          <TextField
            fullWidth
            label="Search products by name or SKU"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            slotProps={{
              input: { startAdornment: <SearchOutlined sx={{ mr: 1 }} /> },
            }}
            sx={{ mb: 2 }}
          />
          {stocks.isError && (
            <Alert severity="error">{stocks.error.message}</Alert>
          )}
          <div className="pos-products">
            {results.map((v) => {
              const s = stocks.data?.find((s) => s.variant_id === v.id);
              return (
                <Paper key={v.id} variant="outlined" className="pos-product">
                  <span className="eyebrow small">{v.category}</span>
                  <strong>{v.name}</strong>
                  <Typography variant="body2" color="text.secondary">
                    {v.label}
                  </Typography>
                  <small>
                    {v.sku} · {s ? quantity(s.available) : "—"} available
                  </small>
                  <Stack
                    direction="row"
                    justifyContent="space-between"
                    alignItems="center"
                  >
                    <b>{money(v.price)}</b>
                    <Button
                      onClick={() => add(v.id)}
                      disabled={!hasShift || scanBusy || !s || Number(s.available) < Number(v.min_qty)}
                    >
                      Add +
                    </Button>
                  </Stack>
                </Paper>
              );
            })}
          </div>
        </div>
        <Paper variant="outlined" className="pos-cart" sx={{ p: 3 }}>
          <Stack direction="row" justifyContent="space-between">
            <Typography variant="h6">Current bill</Typography>
            <Chip label={`${cart.length} items`} size="small" />
          </Stack>
          <Divider sx={{ my: 2 }} />
          {!items.length && (
            <Typography
              color="text.secondary"
              sx={{ py: 5, textAlign: "center" }}
            >
              Scan or select a product to start billing.
            </Typography>
          )}
          {items.map((x) => (
            <div className="pos-line" key={x.variant_id}>
              <Stack direction="row" justifyContent="space-between">
                <div>
                  <strong>{x.v.name}</strong>
                  <Typography variant="caption" display="block">
                    {x.v.label} · {money(x.v.price)}/{x.v.unit}
                  </Typography>
                </div>
                <IconButton
                  size="small"
                  aria-label="Remove item"
                  onClick={() =>
                    setCart(cart.filter((c) => c.variant_id !== x.variant_id))
                  }
                >
                  <Close fontSize="small" />
                </IconButton>
              </Stack>
              <Stack
                direction="row"
                alignItems="center"
                justifyContent="space-between"
                sx={{ mt: 1 }}
              >
                <TextField
                  label="Quantity"
                  type="number"
                  value={x.quantity}
                  inputProps={{
                    min: Number(x.v.min_qty),
                    step: Number(x.v.step),
                    max: Number(x.v.max_qty),
                  }}
                  onChange={(e) =>
                    setCart(
                      cart.map((c) =>
                        c.variant_id === x.variant_id
                          ? { ...c, quantity: Number(e.target.value) }
                          : c,
                      ),
                    )
                  }
                  sx={{ width: 110 }}
                />
                <strong>{money(amount(x.v.price, x.quantity))}</strong>
              </Stack>
            </div>
          ))}
          <Divider sx={{ my: 2 }} />
          <div className="total-line grand">
            <strong>Total</strong>
            <strong>{money(total)}</strong>
          </div>
          <Typography variant="caption" color="text.secondary">
            Listed prices are final; no additional tax is calculated in this
            initial version.
          </Typography>
          <TextField
            fullWidth
            label="Customer mobile number"
            value={customerMobile}
            onChange={(e) => {
              setCustomerMobile(e.target.value.replace(/\D/g, "").slice(0, 10));
              setError("");
            }}
            inputProps={{
              inputMode: "numeric",
              pattern: "[0-9]*",
              maxLength: 10,
            }}
            helperText={
              customerMobile.length === 10
                ? customerLookup.isFetching
                  ? "Looking up customer…"
                  : customerLookup.data?.found
                    ? "Returning customer found"
                    : "New customer — enter their name"
                : "Enter a 10-digit Indian mobile number"
            }
            sx={{ mt: 2 }}
          />
          <TextField
            fullWidth
            label="Customer name"
            value={customerName}
            onChange={(e) => setCustomerName(e.target.value)}
            disabled={customerLookup.data?.found === true}
            helperText={
              customerLookup.data?.found
                ? "Name fetched from the customer record"
                : "Saved securely when this sale is completed"
            }
            sx={{ mt: 1 }}
          />
          <TextField
            select
            fullWidth
            label="Payment method"
            value={paymentMethod}
            onChange={(e) => {
              setPaymentMethod(
                e.target.value as "cash" | "card" | "upi" | "split",
              );
              setAmountTendered("");
              setSplitCash("");
              setSplitCard("");
              setSplitUpi("");
              setError("");
            }}
            sx={{ mt: 2 }}
          >
            <MenuItem value="cash">Cash</MenuItem>
            <MenuItem value="card">Card</MenuItem>
            <MenuItem value="upi">UPI</MenuItem>
            <MenuItem value="split">Split payment</MenuItem>
          </TextField>
          {paymentMethod === "cash" && (
            <>
              <TextField
                fullWidth
                type="number"
                label="Cash received"
                value={amountTendered}
                onChange={(e) => setAmountTendered(e.target.value)}
                inputProps={{ min: 0, step: 0.01 }}
                sx={{ mt: 2 }}
              />
              {amountTendered !== "" && (
                <Alert
                  severity={paymentValid ? "success" : "warning"}
                  sx={{ mt: 2 }}
                >
                  {paymentValid
                    ? `Balance to return: ${money(Number(amountTendered) - total)}`
                    : `Cash received is ${money(total - Number(amountTendered))} short.`}
                </Alert>
              )}
            </>
          )}
          {paymentMethod === "split" && (
            <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
                Split the bill total across payment methods
              </Typography>
              <Stack spacing={1.5}>
                <TextField type="number" label="Cash portion" value={splitCash} onChange={(e) => setSplitCash(e.target.value)} inputProps={{ min: 0, step: 0.01 }} />
                <TextField type="number" label="Card portion" value={splitCard} onChange={(e) => setSplitCard(e.target.value)} inputProps={{ min: 0, step: 0.01 }} />
                <TextField type="number" label="UPI portion" value={splitUpi} onChange={(e) => setSplitUpi(e.target.value)} inputProps={{ min: 0, step: 0.01 }} />
                <Alert severity={paymentValid ? "success" : "warning"}>
                  Allocated: {money(splitTotal)} · Remaining: {money(Math.max(0, total - splitTotal))}
                  {splitTotal > total ? ` · Excess allocation: ${money(splitTotal - total)}` : ""}
                </Alert>
              </Stack>
            </Paper>
          )}
          {error && (
            <Alert severity="error" sx={{ my: 2 }}>
              {error}
            </Alert>
          )}
          <Button
            fullWidth
            variant="contained"
            size="large"
            sx={{ mt: 2 }}
            disabled={
              !items.length || busy || !hasShift || !paymentValid || !customerValid
            }
            onClick={() => void complete()}
          >
            {busy
              ? "Completing…"
              : paymentMethod === "cash"
                ? "Confirm cash & complete"
                : paymentMethod === "split"
                  ? "Confirm split payment & complete"
                : `Confirm ${paymentMethod.toUpperCase()} payment & complete`}
          </Button>
          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            <Button onClick={hold} disabled={busy}>
              Hold bill
            </Button>
            <Button onClick={resume} disabled={busy}>
              Resume held bill
            </Button>
            <Button
              color="inherit"
              disabled={busy}
              onClick={async () => {
                if (
                  await confirmation.ask(
                    "Remove every item from the current bill?",
                    {
                      title: "Clear current bill",
                      confirmLabel: "Clear bill",
                      danger: true,
                    },
                  )
                )
                  setCart([]);
              }}
            >
              Clear
            </Button>
          </Stack>
        </Paper>
      </div>
      <Dialog
        open={!!pendingLoose}
        onClose={() => {
          setPendingLoose(null);
          setLooseQuantity("");
          setTimeout(() => scanRef.current?.focus(), 0);
        }}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>Enter loose quantity</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Typography>
              <strong>{pendingLoose?.name}</strong>
              <br />
              {pendingLoose?.label}
            </Typography>
            <TextField
              autoFocus
              fullWidth
              type="number"
              label={
                pendingLoose?.unit === "kg" ? "Weight (kg)" : "Volume (litre)"
              }
              value={looseQuantity}
              onChange={(e) => setLooseQuantity(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !looseValidation()) {
                  e.preventDefault();
                  addLoose();
                }
              }}
              inputProps={{
                min: Number(pendingLoose?.min_qty || 0),
                step: Number(pendingLoose?.step || 0.001),
                max: Number(pendingLoose?.available || 0),
              }}
              error={looseQuantity !== "" && !!looseValidation()}
              helperText={
                (looseQuantity !== "" && looseValidation()) ||
                `Available: ${quantity(pendingLoose?.available || 0)} ${pendingLoose?.unit || ""} · increments of ${quantity(pendingLoose?.step || 0)}`
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setPendingLoose(null);
              setLooseQuantity("");
              setTimeout(() => scanRef.current?.focus(), 0);
            }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            disabled={!!looseValidation()}
            onClick={addLoose}
          >
            Add to bill
          </Button>
        </DialogActions>
      </Dialog>
      <Receipt receipt={receipt} close={() => setReceipt(null)} />
      {confirmation.confirmationDialog}
    </>
  );
  return (
    <>
      <Heading
        title="Point of sale"
        subtitle="Scan, add, and bill. Prices and stock are checked on completion."
        action={
          <Chip label="Cash billing" color="primary" variant="outlined" />
        }
      />
      {confirmation.confirmationDialog}
    </>
  );
}

function Receipt({
  receipt,
  close,
}: {
  receipt: Sale | null;
  close: () => void;
}) {
  return (
    <Dialog open={!!receipt} onClose={close} maxWidth="xs" fullWidth>
      <DialogTitle>Sale receipt</DialogTitle>
      <DialogContent>
        {receipt && (
          <div className="print-receipt">
            <h2>CHINNU</h2>
            <p>
              {receipt.branch_name}
              <br />
              {receipt.number}
              <br />
              {date(receipt.created_at)}
              <br />
              {receipt.customer_name} · {receipt.customer_code}
            </p>
            <Divider sx={{ my: 2 }} />
            {receipt.items.map((i) => (
              <div key={i.id} className="total-line">
                <span>
                  {i.name}
                  <br />
                  <small>
                    {quantity(i.quantity)} {i.unit} × {money(i.price)}
                  </small>
                </span>
                <strong>{money(i.line_total)}</strong>
              </div>
            ))}
            <Divider sx={{ my: 2 }} />
            <div className="total-line">
              <strong>
                Total paid · {receipt.payment_method.toUpperCase()}
              </strong>
              <strong>{money(receipt.total)}</strong>
            </div>
            {receipt.payments.map((payment) => (
              <div className="total-line" key={payment.method}>
                <span>{payment.method.toUpperCase()}</span>
                <strong>{money(payment.amount)}</strong>
              </div>
            ))}
            {receipt.payments.some((payment) => payment.method === "cash") && (
              <>
                <div className="total-line">
                  <span>Cash received</span>
                  <strong>
                    {money(receipt.amount_tendered || receipt.total)}
                  </strong>
                </div>
                <div className="total-line">
                  <span>Balance returned</span>
                  <strong>{money(receipt.change_due)}</strong>
                </div>
              </>
            )}
            <p>Thank you for shopping with CHINNU.</p>
          </div>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={close}>Close</Button>
        <Button onClick={() => window.print()} variant="contained">
          Print receipt
        </Button>
      </DialogActions>
    </Dialog>
  );
}
function OnlineReceipt({
  order,
  close,
}: {
  order: Order | null;
  close: () => void;
}) {
  return (
    <Dialog open={!!order} onClose={close} maxWidth="xs" fullWidth>
      <DialogTitle>Online sales receipt</DialogTitle>
      <DialogContent>
        {order && (
          <div className="print-receipt">
            <h2>CHINNU</h2>
            <p>
              {order.branch_name}
              <br />
              {order.number}
              <br />
              {date(order.created_at)}
              <br />
              {order.customer_name}
            </p>
            <Divider sx={{ my: 2 }} />
            {order.items.map((i) => (
              <div key={i.id} className="total-line">
                <span>
                  {i.name}
                  <br />
                  <small>
                    {quantity(i.quantity)} {i.unit} × {money(i.price)}
                  </small>
                </span>
                <strong>{money(i.line_total)}</strong>
              </div>
            ))}
            <Divider sx={{ my: 2 }} />
            <div className="total-line">
              <span>Delivery charge</span>
              <strong>{money(order.delivery_fee)}</strong>
            </div>
            <div className="total-line">
              <strong>Total paid · ONLINE</strong>
              <strong>{money(order.total)}</strong>
            </div>
            {order.payment_collection && <OrderPaymentSummary collection={order.payment_collection} />}
            <p>
              {order.method === "delivery"
                ? `Delivered to: ${order.address}`
                : "Shop pickup"}
              <br />
              Thank you for shopping with CHINNU.
            </p>
          </div>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={close}>Close</Button>
        <Button onClick={() => window.print()} variant="contained">
          Print receipt
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function BranchOrders({ branch }: { branch: number }) {
  const defaultRejectionReason =
    "We are unable to fulfil this order because the requested items are currently unavailable or due to an operational issue. Please contact the branch for assistance.";
  const { notify, user } = useApp(),
    qc = useQueryClient();
  const [filter, setFilter] = useState("active"),
    [selected, setSelected] = useState<Order | null>(null),
    [code, setCode] = useState(""),
    [deliveryCharge, setDeliveryCharge] = useState(""),
    [deliveryDays, setDeliveryDays] = useState(""),
    [rejectionReason, setRejectionReason] = useState(""),
    [rejectOpen, setRejectOpen] = useState(false),
    [deliveryUser, setDeliveryUser] = useState(""),
    [busy, setBusy] = useState(false);
  const confirmation = useConfirmDialog();
  const query = useQuery({
    queryKey: ["staff-orders", branch],
    queryFn: () =>
      api<Order[]>(branch ? `/orders?branch_id=${branch}` : "/orders"),
    refetchInterval: 15000,
  });
  const current = query.data?.find((o) => o.id === selected?.id) || selected;
  const deliveryStaff = useQuery({
    queryKey: ["delivery-staff", current?.branch_id],
    queryFn: () => api<User[]>(`/delivery/staff?branch_id=${current!.branch_id}`),
    enabled: !!current && current.method === "delivery" && current.status === "ready",
  });
  async function action(action: string) {
    if (!current) return;
    if (action === "reject") {
      if (!rejectionReason.trim())
        setRejectionReason(defaultRejectionReason);
      setRejectOpen(true);
      return;
    }
    if (
      action === "approve_coverage" &&
      !(await confirmation.ask(
        `Approve delivery with a ${money(deliveryCharge)} charge and an estimate of ${deliveryDays} day(s)?`,
        { title: "Approve delivery", confirmLabel: "Approve" },
      ))
    )
      return;
    setBusy(true);
    try {
      await post(
        `/orders/${current.id}/transition`,
        {
          action,
          ...(action === "collect" ? { pickup_code: code } : {}),
          ...(action === "approve_coverage"
            ? {
                delivery_charge: deliveryCharge,
                estimated_delivery_days: Number(deliveryDays),
              }
            : {}),
        },
        key(),
      );
      await qc.invalidateQueries();
      notify("Order updated");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function rejectOrder() {
    if (!current || rejectionReason.trim().length < 3) return;
    setBusy(true);
    try {
      await post(
        `/orders/${current.id}/transition`,
        { action: "reject", note: rejectionReason.trim() },
        key(),
      );
      setRejectOpen(false);
      setSelected(null);
      await qc.invalidateQueries();
      notify("Order rejected and the customer can see the reason.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function assignDelivery() {
    if (!current || !deliveryUser) return;
    setBusy(true);
    try {
      await post(`/orders/${current.id}/assign-delivery`, {
        delivery_user_id: Number(deliveryUser),
      });
      await qc.invalidateQueries();
      notify("Delivery person assigned.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const pendingApprovals = (query.data || []).filter(
    (o) => o.status === "approval_pending",
  );
  const rejectionReasonFor = (order: Order) =>
    (order.display_status || order.status) === "rejected"
      ? [...order.events].reverse().find((event) => event.note?.trim())?.note ||
        "No rejection reason was recorded."
      : "—";
  const rows = (query.data || []).filter(
    (o) =>
      filter === "all" ||
      (filter === "active"
        ? !["completed", "cancelled"].includes(o.status)
        : (o.display_status || o.status) === filter),
  );
  const statusCount = (status: string) => {
    const orders = query.data || [];
    if (status === "all") return orders.length;
    if (status === "active")
      return orders.filter(
        (order) =>
          !["completed", "rejected", "cancelled"].includes(
            order.display_status || order.status,
          ),
      ).length;
    return orders.filter(
      (order) => (order.display_status || order.status) === status,
    ).length;
  };
  const statusBadgeColor: Record<string, string> = {
    active: "#20744a",
    approval_pending: "#d97706",
    placed: "#2563eb",
    confirmed: "#0f766e",
    preparing: "#7c3aed",
    ready: "#0891b2",
    dispatched: "#4f46e5",
    completed: "#15803d",
    rejected: "#dc2626",
    cancelled: "#64748b",
    all: "#24372e",
  };
  return (
    <>
      <Heading
        title="Online orders"
        subtitle="A shared queue from placement to handover."
      />
      {pendingApprovals.length > 0 && (
        <Alert
          severity="warning"
          variant="filled"
          sx={{ mb: 2, alignItems: "center" }}
          action={
            <Button
              color="inherit"
              size="small"
              onClick={() => setFilter("approval_pending")}
            >
              Review now
            </Button>
          }
        >
          <strong>
            {pendingApprovals.length} order
            {pendingApprovals.length === 1 ? "" : "s"} outside the coverage area
          </strong>
          <br />
          Manager approval, delivery charge, and estimated delivery days are
          required.
        </Alert>
      )}
      <Stack
        direction="row"
        spacing={1.5}
        sx={{ mb: 2, pt: 1, pr: 1, overflowX: "auto", overflowY: "hidden" }}
      >
        {[
          "active",
          "approval_pending",
          "placed",
          "confirmed",
          "preparing",
          "ready",
          "dispatched",
          "completed",
          "rejected",
          "cancelled",
          "all",
        ].map((f) => (
          <Badge
            key={f}
            badgeContent={statusCount(f)}
            showZero
            overlap="rectangular"
            sx={{
              flexShrink: 0,
              "& .MuiBadge-badge": {
                bgcolor: statusBadgeColor[f],
                color: "#fff",
                fontWeight: 800,
                fontSize: 11,
                minWidth: 21,
                height: 21,
                px: 0.65,
                border: "2px solid #fff",
                boxShadow: "0 2px 6px rgba(20,45,32,.22)",
                top: 2,
                right: 3,
              },
            }}
          >
            <Chip
              label={f.replaceAll("_", " ")}
              color={filter === f ? "primary" : "default"}
              onClick={() => setFilter(f)}
              sx={{ pr: 0.5 }}
            />
          </Badge>
        ))}
      </Stack>
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}
      <DataTable
        rows={rows}
        columns={[
          { label: "Order", value: (o) => <strong>{o.number}</strong> },
          ...(branch === 0
            ? [{ label: "Branch", value: (o: Order) => o.branch_name }]
            : []),
          { label: "Customer", value: (o) => o.customer_name },
          { label: "Method", value: (o) => o.method },
          { label: "Total", value: (o) => money(o.total) },
          {
            label: "Payment",
            value: (o) => <Status value={o.payment_status} />,
          },
          {
            label: "Status",
            value: (o) => <Status value={o.display_status || o.status} />,
          },
          {
            label: "Rejection reason",
            value: (o) => (
              <Typography
                variant="body2"
                color={
                  (o.display_status || o.status) === "rejected"
                    ? "error.main"
                    : "text.secondary"
                }
                sx={{ maxWidth: 280 }}
              >
                {rejectionReasonFor(o)}
              </Typography>
            ),
          },
          {
            label: "Action",
            value: (o) => (
              <Button
                onClick={() => {
                  setSelected(o);
                  setCode("");
                  setDeliveryCharge("");
                  setDeliveryDays("");
                  setRejectionReason("");
                  setDeliveryUser(String(o.assigned_delivery_user_id || ""));
                }}
              >
                Open order
              </Button>
            ),
          },
        ]}
      />
      <Dialog
        open={rejectOpen}
        onClose={() => !busy && setRejectOpen(false)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>Reject order</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            The order will be rejected, its reserved stock released, and your
            reason will be shown to the customer.
          </Alert>
          <TextField
            autoFocus
            fullWidth
            multiline
            minRows={3}
            label="Rejection reason"
            value={rejectionReason}
            onChange={(e) => setRejectionReason(e.target.value)}
            error={
              rejectionReason.length > 0 && rejectionReason.trim().length < 3
            }
            helperText="Required · 3–500 characters"
            inputProps={{ maxLength: 500 }}
          />
        </DialogContent>
        <DialogActions>
          <Button disabled={busy} onClick={() => setRejectOpen(false)}>
            Back
          </Button>
          <Button
            disabled={busy || rejectionReason.trim().length < 3}
            color="error"
            variant="contained"
            onClick={() => void rejectOrder()}
          >
            {busy ? "Rejecting…" : "Reject order"}
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={!!current}
        onClose={() => setSelected(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>{current?.number}</DialogTitle>
        <DialogContent>
          {current && (
            <Stack spacing={2}>
              <Typography>
                {current.customer_name} · {current.phone}
              </Typography>
              <Typography variant="body2">
                {current.method === "delivery"
                  ? current.address
                  : current.branch_address}
              </Typography>
              <Status value={current.display_status || current.status} />
              {(current.display_status || current.status) === "rejected" && (
                <Alert severity="error">
                  <strong>Rejection reason:</strong>{" "}
                  {rejectionReasonFor(current)}
                </Alert>
              )}
              {current.status === "approval_pending" && (
                <>
                  <Alert severity="warning">
                    This address is {current.delivery_distance_km} km from the
                    branch and is outside its normal coverage. A manager must
                    decide before{" "}
                    {current.approval_expires_at
                      ? date(current.approval_expires_at)
                      : "the 24-hour deadline"}
                    .
                  </Alert>
                  {["admin", "manager"].includes(user!.role) && (
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                      <TextField
                        fullWidth
                        type="number"
                        label="Delivery charge"
                        value={deliveryCharge}
                        onChange={(e) => setDeliveryCharge(e.target.value)}
                        inputProps={{ min: 0, max: 100000, step: 0.01 }}
                      />
                      <TextField
                        fullWidth
                        type="number"
                        label="Estimated delivery (days)"
                        value={deliveryDays}
                        onChange={(e) => setDeliveryDays(e.target.value)}
                        inputProps={{ min: 1, max: 60, step: 1 }}
                      />
                    </Stack>
                  )}
                </>
              )}
              {current.coverage_approved_at && (
                <Alert severity="success">
                  Outside-coverage delivery approved · Charge{" "}
                  {money(current.delivery_fee)} · Estimated{" "}
                  {current.estimated_delivery_days} day(s).
                </Alert>
              )}
              {current.items.map((i) => (
                <div className="total-line" key={i.id}>
                  <span>
                    {i.name} × {quantity(i.quantity)} {i.unit}
                  </span>
                  <strong>{money(i.line_total)}</strong>
                </div>
              ))}
              <Divider />
              <div className="total-line">
                <span>Total including delivery</span>
                <strong>{money(current.total)}</strong>
              </div>
              <OrderPaymentPanel key={current.id} order={current} />
              {current.expires_at && current.status === "placed" && (
                <Alert severity="warning">
                  Confirm before {date(current.expires_at)} to retain the
                  reservation.
                </Alert>
              )}
              {current.method === "pickup" && current.status === "ready" && (
                <TextField
                  label="Customer pickup code"
                  value={code}
                  onChange={(e) =>
                    setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                  }
                  inputProps={{ inputMode: "numeric", maxLength: 6 }}
                  error={code.length > 0 && code.length !== 6}
                  helperText="Enter the customer's six-digit pickup code."
                />
              )}
              {current.method === "delivery" && current.status === "ready" && (
                <TextField
                  select
                  label="Assign delivery person"
                  value={deliveryUser}
                  onChange={(e) => setDeliveryUser(e.target.value)}
                  helperText={deliveryStaff.data?.length ? "The assigned order will appear in the delivery app." : "Create an active delivery staff account for this branch first."}
                >
                  {(deliveryStaff.data || []).map((driver) => (
                    <MenuItem value={driver.id} key={driver.id}>{driver.name}</MenuItem>
                  ))}
                </TextField>
              )}
              <Typography variant="subtitle2">Order history</Typography>
              {current.events.map((e) => (
                <Typography key={e.id} variant="body2" color="text.secondary">
                  {date(e.created_at)} · {e.status} {e.note && `— ${e.note}`}
                </Typography>
              ))}
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ flexWrap: "wrap", gap: 1 }}>
          <Button onClick={() => setSelected(null)}>Close</Button>
          {current && (
            <>
              {current.status === "approval_pending" &&
                ["admin", "manager"].includes(user!.role) && (
                  <>
                    <Button
                      disabled={busy}
                      color="error"
                      onClick={() => void action("reject")}
                    >
                      Reject delivery
                    </Button>
                    <Button
                      disabled={
                        busy ||
                        deliveryCharge === "" ||
                        Number(deliveryCharge) < 0 ||
                        !Number.isInteger(Number(deliveryDays)) ||
                        Number(deliveryDays) < 1 ||
                        Number(deliveryDays) > 60
                      }
                      variant="contained"
                      onClick={() => void action("approve_coverage")}
                    >
                      Approve delivery
                    </Button>
                  </>
                )}
              {current.status === "placed" && (
                <Button
                  disabled={busy}
                  variant="contained"
                  onClick={() => void action("confirm")}
                >
                  Confirm order
                </Button>
              )}
              {current.status === "confirmed" && (
                <Button
                  disabled={busy}
                  variant="contained"
                  onClick={() => void action("prepare")}
                >
                  Start preparing
                </Button>
              )}
              {current.status === "preparing" && (
                <Button
                  disabled={busy}
                  variant="contained"
                  onClick={() => void action("ready")}
                >
                  Mark ready
                </Button>
              )}
              {current.status === "ready" && current.method === "delivery" && (
                <Button disabled={busy || !deliveryUser} variant="contained" onClick={() => void assignDelivery()}>
                  {current.assigned_delivery_user_id ? "Update assignment" : "Assign delivery"}
                </Button>
              )}
              {current.status === "ready" && current.method === "pickup" && (
                <Button
                  disabled={
                    busy ||
                    !/^[0-9]{6}$/.test(code) ||
                    current.payment_status !== "paid"
                  }
                  variant="contained"
                  onClick={() => void action("collect")}
                >
                  Verify & hand over
                </Button>
              )}
              {current.status === "dispatched" && (
                <Button
                  disabled={busy || current.payment_status !== "paid"}
                  variant="contained"
                  onClick={() => void action("deliver")}
                >
                  Confirm delivered
                </Button>
              )}
              {["placed", "confirmed", "preparing", "ready"].includes(
                current.status,
              ) &&
                current.payment_status === "unpaid" && (
                  <Button
                    disabled={busy}
                    color="error"
                    onClick={() => void action("reject")}
                  >
                    Reject order
                  </Button>
                )}
            </>
          )}
        </DialogActions>
      </Dialog>
      {confirmation.confirmationDialog}
    </>
  );
}

function Inventory({ branch }: { branch: number }) {
  const { user, notify } = useApp(),
    qc = useQueryClient();
  const [search, setSearch] = useState(""),
    [low, setLow] = useState(false),
    [threshold, setThreshold] = useState(""),
    [comparison, setComparison] = useState<"lt" | "gt">("lt"),
    [selected, setSelected] = useState<Stock | null>(null),
    [kind, setKind] = useState("receive"),
    [qty, setQty] = useState("1"),
    [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false),
    [history, setHistory] = useState(false);
  const thresholdQuery =
    threshold === ""
      ? ""
      : `&threshold=${encodeURIComponent(threshold)}&comparison=${comparison}`;
  const query = useQuery({
    queryKey: ["inventory", branch, threshold, comparison],
    queryFn: () =>
      api<Stock[]>(
        `/inventory${branch ? `?branch_id=${branch}` : ""}${thresholdQuery.replace("&", branch ? "&" : "?")}`,
      ),
    enabled: threshold === "" || Number(threshold) >= 0,
  });
  const ledger = useQuery({
    queryKey: ["movements", branch],
    queryFn: () =>
      api<
        {
          id: number;
          branch_name: string;
          name: string;
          delta: string;
          kind: string;
          reference: string;
          reason: string;
          created_at: string;
        }[]
      >(branch ? `/movements?branch_id=${branch}` : "/movements"),
    enabled: history,
  });
  const rows = (query.data || []).filter(
    (s) =>
      (!low || s.low) &&
      (s.name + " " + s.sku).toLowerCase().includes(search.toLowerCase()),
  );
  async function save() {
    if (!selected) return;
    setBusy(true);
    try {
      await post(
        "/inventory/change",
        {
          branch_id: selected.branch_id,
          variant_id: selected.variant_id,
          quantity: qty,
          kind,
          reason,
        },
        key(),
      );
      setSelected(null);
      setReason("");
      await qc.invalidateQueries();
      notify("Stock updated with a movement record.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        title="Branch inventory"
        subtitle="Available = on-hand − reserved − damaged. Quantities use the variant's selling unit."
        action={
          <Button variant="outlined" onClick={() => setHistory(!history)}>
            {history ? "Show stock" : "Movement history"}
          </Button>
        }
      />
      {history ? (
        <>
          {ledger.isError && (
            <Alert severity="error">{ledger.error.message}</Alert>
          )}
          <DataTable
            rows={ledger.data || []}
            columns={[
              { label: "Time", value: (m) => date(m.created_at) },
              ...(branch === 0
                ? [
                    {
                      label: "Branch",
                      value: (m: { branch_name: string }) => m.branch_name,
                    },
                  ]
                : []),
              { label: "Product", value: (m) => m.name },
              { label: "Event", value: (m) => m.kind },
              { label: "Change", value: (m) => quantity(m.delta) },
              { label: "Reference", value: (m) => m.reference },
              { label: "Reason", value: (m) => m.reason },
            ]}
          />
        </>
      ) : (
        <>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            gap={2}
            sx={{ mb: 2, alignItems: { sm: "center" } }}
          >
            <TextField
              label="Search name or SKU"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <TextField
              select
              label="Available stock"
              value={comparison}
              onChange={(e) => setComparison(e.target.value as "lt" | "gt")}
              sx={{ minWidth: 170 }}
            >
              <MenuItem value="lt">Lower than</MenuItem>
              <MenuItem value="gt">Greater than</MenuItem>
            </TextField>
            <TextField
              type="number"
              label="Threshold value"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              error={threshold !== "" && Number(threshold) < 0}
              helperText={
                threshold === ""
                  ? "No threshold filter"
                  : Number(threshold) < 0
                    ? "Enter zero or greater"
                    : "Backend-filtered"
              }
              inputProps={{ min: 0, step: 0.001 }}
              sx={{ width: { xs: "100%", sm: 180 } }}
            />
            {threshold !== "" && (
              <Button color="inherit" onClick={() => setThreshold("")}>
                Clear threshold
              </Button>
            )}
            <Chip
              label="Low stock only"
              color={low ? "primary" : "default"}
              onClick={() => setLow(!low)}
            />
          </Stack>
          {query.isError && (
            <Alert severity="error">{query.error.message}</Alert>
          )}
          <DataTable
            rows={rows}
            columns={[
              ...(branch === 0
                ? [{ label: "Branch", value: (s: Stock) => s.branch_name }]
                : []),
              {
                label: "Product / variant",
                value: (s) => (
                  <>
                    <strong>{s.name}</strong>
                    <Typography variant="caption" display="block">
                      {s.label} · {s.sku}
                    </Typography>
                  </>
                ),
              },
              {
                label: "On-hand",
                value: (s) => `${quantity(s.on_hand)} ${s.unit}`,
              },
              { label: "Reserved", value: (s) => quantity(s.reserved) },
              { label: "Damaged", value: (s) => quantity(s.damaged) },
              {
                label: "Available",
                value: (s) => (
                  <Chip
                    label={quantity(s.available)}
                    color={s.low ? "warning" : "default"}
                    size="small"
                  />
                ),
              },
              {
                label: "Action",
                value: (s) =>
                  user?.role === "cashier" ? (
                    "View only"
                  ) : (
                    <Button
                      onClick={() => {
                        setSelected(s);
                        setKind("receive");
                        setQty("1");
                      }}
                    >
                      Update stock
                    </Button>
                  ),
              },
            ]}
          />
        </>
      )}
      <Dialog
        open={!!selected}
        onClose={() => setSelected(null)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>{selected?.name}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              select
              label="Operation"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              <MenuItem value="receive">Receive goods</MenuItem>
              <MenuItem value="damage">Mark damaged / unsellable</MenuItem>
              {["admin", "manager"].includes(user!.role) && (
                <MenuItem value="adjust_up">Adjustment · increase</MenuItem>
              )}
              {["admin", "manager"].includes(user!.role) && (
                <MenuItem value="adjust_down">Adjustment · decrease</MenuItem>
              )}
            </TextField>
            <TextField
              type="number"
              label={`Quantity (${selected?.unit})`}
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              inputProps={{ min: 0.001, step: 0.001 }}
            />
            <TextField
              label="Reason or supplier reference"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              multiline
              minRows={2}
            />
            <Typography variant="caption" color="text.secondary">
              Enter a change quantity. A positive adjustment of 3 adds 3; it
              does not set the total to 3.
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelected(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={busy || Number(qty) <= 0 || reason.trim().length < 3}
            onClick={() => void save()}
          >
            Save movement
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

type ReturnExchangeResult = {
  id: number;
  number: string;
  original_receipt: string;
  branch_name: string;
  customer_name: string;
  customer_code: string;
  kind: string;
  returned_items: {
    name: string;
    quantity: string;
    unit: string;
    line_total: string;
    condition: string;
  }[];
  replacement_items: {
    name: string;
    quantity: string;
    unit: string;
    line_total: string;
  }[];
  return_total: string;
  replacement_total: string;
  amount_due: string;
  refund_due: string;
  settlement_method: string;
  amount_tendered: string | null;
  change_due: string;
  reason: string;
  created_at: string;
};
type ExchangeQuote = {
  return_total: string;
  replacement_total: string;
  amount_due: string;
  refund_due: string;
  fingerprint: string;
};
function ExchangeReceipt({
  receipt,
  close,
}: {
  receipt: ReturnExchangeResult | null;
  close: () => void;
}) {
  return (
    <Dialog open={!!receipt} onClose={close} fullWidth maxWidth="sm">
      <DialogTitle>
        {receipt?.kind === "exchange" ? "Exchange receipt" : "Return receipt"}
      </DialogTitle>
      <DialogContent>
        {receipt && (
          <div className="print-receipt">
            <h2>CHINNU</h2>
            <p>
              {receipt.number}
              <br />
              Original: {receipt.original_receipt}
              <br />
              {receipt.customer_name} · {receipt.customer_code}
              <br />
              {date(receipt.created_at)}
            </p>
            <Divider />
            <Typography variant="subtitle2">RETURNED</Typography>
            {receipt.returned_items.map((x, i) => (
              <div className="total-line" key={i}>
                <span>
                  {x.name} × {quantity(x.quantity)} {x.unit}
                  <br />
                  <small>{x.condition}</small>
                </span>
                <strong>{money(x.line_total)}</strong>
              </div>
            ))}
            {receipt.replacement_items.length > 0 && (
              <>
                <Divider />
                <Typography variant="subtitle2">NEW ITEMS</Typography>
                {receipt.replacement_items.map((x, i) => (
                  <div className="total-line" key={i}>
                    <span>
                      {x.name} × {quantity(x.quantity)} {x.unit}
                    </span>
                    <strong>{money(x.line_total)}</strong>
                  </div>
                ))}
              </>
            )}
            <Divider />
            <div className="total-line">
              <span>Return credit</span>
              <strong>{money(receipt.return_total)}</strong>
            </div>
            <div className="total-line">
              <span>New items total</span>
              <strong>{money(receipt.replacement_total)}</strong>
            </div>
            <div className="total-line">
              <strong>
                {Number(receipt.amount_due) > 0
                  ? "Customer paid"
                  : Number(receipt.refund_due) > 0
                    ? "Refunded"
                    : "Even exchange"}
              </strong>
              <strong>
                {money(
                  Number(receipt.amount_due) > 0
                    ? receipt.amount_due
                    : receipt.refund_due,
                )}
              </strong>
            </div>
            {receipt.settlement_method === "cash" &&
              receipt.amount_tendered && (
                <>
                  <div className="total-line">
                    <span>Cash received</span>
                    <strong>{money(receipt.amount_tendered)}</strong>
                  </div>
                  <div className="total-line">
                    <span>Balance returned</span>
                    <strong>{money(receipt.change_due)}</strong>
                  </div>
                </>
              )}
            <p>
              Settlement: {receipt.settlement_method.toUpperCase()}
              <br />
              {receipt.reason}
            </p>
          </div>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={close}>Close</Button>
        <Button variant="contained" onClick={() => window.print()}>
          Print receipt
        </Button>
      </DialogActions>
    </Dialog>
  );
}
function Sales({ branch }: { branch: number }) {
  const { user, catalogue, notify } = useApp(),
    qc = useQueryClient();
  const [channel, setChannel] = useState<"pos" | "online" | "exchange">("pos"),
    [receipt, setReceipt] = useState<Sale | null>(null),
    [onlineReceipt, setOnlineReceipt] = useState<Order | null>(null),
    [search, setSearch] = useState(""),
    [matches, setMatches] = useState<Sale[]>([]),
    [selected, setSelected] = useState<Sale | null>(null),
    [item, setItem] = useState(0),
    [returnQty, setReturnQty] = useState("1"),
    [condition, setCondition] = useState<"sellable" | "damaged">("sellable"),
    [reason, setReason] = useState(""),
    [method, setMethod] = useState<"cash" | "card" | "upi">("cash"),
    [replacementVariant, setReplacementVariant] = useState(""),
    [replacementQty, setReplacementQty] = useState("1"),
    [replacements, setReplacements] = useState<
      { variant_id: number; quantity: number; name: string }[]
    >([]),
    [quote, setQuote] = useState<ExchangeQuote | null>(null),
    [cashReceived, setCashReceived] = useState(""),
    [result, setResult] = useState<ReturnExchangeResult | null>(null),
    [busy, setBusy] = useState(false);
  const query = useQuery({
    queryKey: ["sales", branch],
    queryFn: () =>
      api<Sale[]>(branch ? `/sales?branch_id=${branch}` : "/sales"),
  });
  const onlineSales = useQuery({
    queryKey: ["online-sales", branch],
    queryFn: () =>
      api<Order[]>(
        branch ? `/online-sales?branch_id=${branch}` : "/online-sales",
      ),
  });
  const exchangeReceipts = useQuery({
    queryKey: ["return-exchanges", branch, "exchange"],
    queryFn: () =>
      api<ReturnExchangeResult[]>(
        `/return-exchanges?${branch ? `branch_id=${branch}&` : ""}kind=exchange`,
      ),
  });
  const variants = catalogue.flatMap((p) =>
    p.variants.map((v) => ({ ...v, name: p.name + " · " + v.label })),
  );
  async function findSales() {
    setBusy(true);
    try {
      const found = await api<Sale[]>(
        `/return-sales?${branch ? `branch_id=${branch}&` : ""}q=${encodeURIComponent(search.trim())}`,
      );
      setMatches(found);
      if (!found.length) notify("No matching receipt was found.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function start(s: Sale) {
    const first = s.items.find((i) => Number(i.quantity) > Number(i.returned));
    setSelected(s);
    setItem(first?.id || 0);
    setReturnQty(
      first ? String(Number(first.quantity) - Number(first.returned)) : "1",
    );
    setReplacements([]);
    setReason("");
    setCondition("sellable");
    setQuote(null);
    setCashReceived("");
  }
  function addReplacement() {
    const v = variants.find((x) => x.id === Number(replacementVariant));
    if (!v || Number(replacementQty) <= 0) return;
    setReplacements((current) =>
      current.some((x) => x.variant_id === v.id)
        ? current.map((x) =>
            x.variant_id === v.id
              ? { ...x, quantity: x.quantity + Number(replacementQty) }
              : x,
          )
        : [
            ...current,
            {
              variant_id: v.id,
              quantity: Number(replacementQty),
              name: v.name,
            },
          ],
    );
    setReplacementVariant("");
    setReplacementQty("1");
  }
  const fingerprint = JSON.stringify({
    item,
    returnQty,
    condition,
    replacements: replacements.map(({ variant_id, quantity }) => ({
      variant_id,
      quantity,
    })),
    method,
    reason,
  });
  const requestBody = (withCash: boolean) => ({
    returns: [{ item_id: item, quantity: returnQty, condition }],
    replacements: replacements.map(({ variant_id, quantity }) => ({
      variant_id,
      quantity,
    })),
    settlement_method: method,
    reason,
    ...(withCash && method === "cash" && quote && Number(quote.amount_due) > 0
      ? { amount_tendered: cashReceived }
      : {}),
  });
  async function review() {
    if (!selected || !item) return;
    setBusy(true);
    try {
      const totals = await post<Omit<ExchangeQuote, "fingerprint">>(
        `/sales/${selected.id}/return-exchange/quote`,
        requestBody(false),
      );
      setQuote({ ...totals, fingerprint });
      setCashReceived("");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function process() {
    if (!selected || !item || !quote || quote.fingerprint !== fingerprint)
      return;
    setBusy(true);
    try {
      const transaction = await post<ReturnExchangeResult>(
        `/sales/${selected.id}/return-exchange`,
        requestBody(true),
        key(),
      );
      setResult(transaction);
      setSelected(null);
      setMatches([]);
      setSearch("");
      await qc.invalidateQueries();
      notify(
        transaction.kind === "exchange"
          ? "Exchange completed."
          : "Return and refund completed.",
      );
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        title="Sales, returns & exchanges"
        subtitle="Find a purchase by receipt number or customer mobile, then process an authorised return or exchange."
      />
      <Stack direction="row" spacing={1} sx={{ mb: 3, flexWrap: "wrap" }}>
        <Button
          variant={channel === "pos" ? "contained" : "outlined"}
          onClick={() => setChannel("pos")}
        >
          POS
        </Button>
        <Button
          variant={channel === "online" ? "contained" : "outlined"}
          onClick={() => setChannel("online")}
        >
          Online orders
        </Button>
        <Button
          variant={channel === "exchange" ? "contained" : "outlined"}
          onClick={() => setChannel("exchange")}
        >
          Exchange receipts
        </Button>
      </Stack>
      {channel === "pos" && (
        <>
          {["admin", "manager"].includes(user!.role) && (
            <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                <TextField
                  fullWidth
                  label="Receipt number or customer mobile"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && search.trim().length >= 3)
                      void findSales();
                  }}
                />
                <Button
                  variant="contained"
                  disabled={busy || search.trim().length < 3}
                  onClick={() => void findSales()}
                >
                  Find purchase
                </Button>
              </Stack>
              {matches.length > 0 && (
                <Stack spacing={1} sx={{ mt: 2 }}>
                  {matches.map((s) => (
                    <Button
                      key={s.id}
                      variant="outlined"
                      onClick={() => start(s)}
                      sx={{ justifyContent: "space-between" }}
                    >
                      <span>
                        {s.number} · {s.customer_name} · {date(s.created_at)}
                      </span>
                      <span>{money(s.total)}</span>
                    </Button>
                  ))}
                </Stack>
              )}
            </Paper>
          )}
          {query.isError && (
            <Alert severity="error">{query.error.message}</Alert>
          )}
          <Typography variant="h6" sx={{ mb: 1 }}>
            POS sales receipts
          </Typography>
          <DataTable
            rows={query.data || []}
            columns={[
              {
                label: "Receipt",
                value: (s) => (
                  <>
                    <strong>{s.number}</strong>
                    {branch === 0 && (
                      <Typography variant="caption" display="block">
                        {s.branch_name}
                      </Typography>
                    )}
                  </>
                ),
              },
              {
                label: "Customer",
                value: (s) => (
                  <>
                    {s.customer_name}
                    <Typography variant="caption" display="block">
                      {s.customer_code}
                    </Typography>
                  </>
                ),
              },
              { label: "Date", value: (s) => date(s.created_at) },
              { label: "Total", value: (s) => money(s.total) },
              { label: "Returned", value: (s) => money(s.refunded) },
              {
                label: "Actions",
                value: (s) => (
                  <>
                    <Button onClick={() => setReceipt(s)}>Receipt</Button>
                    {["admin", "manager"].includes(user!.role) &&
                      Number(s.refunded) < Number(s.total) && (
                        <Button onClick={() => start(s)}>
                          Return / exchange
                        </Button>
                      )}
                  </>
                ),
              },
            ]}
          />
        </>
      )}
      {channel === "online" && (
        <>
          {onlineSales.isError && (
            <Alert severity="error">{onlineSales.error.message}</Alert>
          )}
          <Typography variant="h6" sx={{ mb: 1 }}>
            Online order receipts
          </Typography>
          <DataTable
            rows={onlineSales.data || []}
            columns={[
              {
                label: "Receipt",
                value: (o) => (
                  <>
                    <strong>{o.number}</strong>
                    {branch === 0 && (
                      <Typography variant="caption" display="block">
                        {o.branch_name}
                      </Typography>
                    )}
                  </>
                ),
              },
              { label: "Customer", value: (o) => o.customer_name },
              { label: "Date", value: (o) => date(o.created_at) },
              { label: "Method", value: (o) => o.method },
              {
                label: "Status",
                value: (o) => <Status value={o.display_status || o.status} />,
              },
              { label: "Total paid", value: (o) => money(o.total) },
              {
                label: "Actions",
                value: (o) => (
                  <Button onClick={() => setOnlineReceipt(o)}>Receipt</Button>
                ),
              },
            ]}
          />
        </>
      )}
      {channel === "exchange" && (
        <>
          {exchangeReceipts.isError && (
            <Alert severity="error">{exchangeReceipts.error.message}</Alert>
          )}
          <Typography variant="h6" sx={{ mb: 1 }}>
            Exchange receipts
          </Typography>
          <DataTable
            rows={exchangeReceipts.data || []}
            columns={[
              {
                label: "Receipt",
                value: (x) => (
                  <>
                    <strong>{x.number}</strong>
                    <Typography variant="caption" display="block">
                      Original: {x.original_receipt}
                    </Typography>
                    {branch === 0 && (
                      <Typography variant="caption" display="block">
                        {x.branch_name}
                      </Typography>
                    )}
                  </>
                ),
              },
              {
                label: "Customer",
                value: (x) => (
                  <>
                    {x.customer_name}
                    <Typography variant="caption" display="block">
                      {x.customer_code}
                    </Typography>
                  </>
                ),
              },
              { label: "Date", value: (x) => date(x.created_at) },
              { label: "Return credit", value: (x) => money(x.return_total) },
              { label: "New items", value: (x) => money(x.replacement_total) },
              {
                label: "Settlement",
                value: (x) => x.settlement_method.toUpperCase(),
              },
              {
                label: "Actions",
                value: (x) => (
                  <Button onClick={() => setResult(x)}>Receipt</Button>
                ),
              },
            ]}
          />
        </>
      )}
      <Receipt receipt={receipt} close={() => setReceipt(null)} />
      <OnlineReceipt
        order={onlineReceipt}
        close={() => setOnlineReceipt(null)}
      />
      <Dialog
        open={!!selected}
        onClose={() => setSelected(null)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>Return or exchange · {selected?.number}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Alert severity="info">
              Returned value uses the original receipt price. Replacement
              products use their current selling price. The backend calculates
              the final payment or refund.
            </Alert>
            <TextField
              select
              label="Product being returned"
              value={item || ""}
              onChange={(e) => {
                const id = Number(e.target.value);
                setItem(id);
                const line = selected?.items.find((i) => i.id === id);
                if (line)
                  setReturnQty(
                    String(Number(line.quantity) - Number(line.returned)),
                  );
              }}
            >
              {selected?.items
                .filter((i) => Number(i.quantity) > Number(i.returned))
                .map((i) => (
                  <MenuItem key={i.id} value={i.id}>
                    {i.name} ·{" "}
                    {quantity(Number(i.quantity) - Number(i.returned))} {i.unit}{" "}
                    returnable
                  </MenuItem>
                ))}
            </TextField>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField
                type="number"
                label="Return quantity"
                value={returnQty}
                onChange={(e) => setReturnQty(e.target.value)}
                inputProps={{ min: 0.001, step: 0.001 }}
              />
              <TextField
                select
                fullWidth
                label="Returned condition"
                value={condition}
                onChange={(e) =>
                  setCondition(e.target.value as "sellable" | "damaged")
                }
              >
                <MenuItem value="sellable">Sellable · restore stock</MenuItem>
                <MenuItem value="damaged">Damaged · unsellable stock</MenuItem>
              </TextField>
            </Stack>
            <Divider />
            <Typography variant="subtitle2">
              Replacement products (optional)
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
              <TextField
                select
                fullWidth
                label="Replacement product"
                value={replacementVariant}
                onChange={(e) => setReplacementVariant(e.target.value)}
              >
                {variants.map((v) => (
                  <MenuItem key={v.id} value={v.id}>
                    {v.name} · {money(v.price)}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                type="number"
                label="Quantity"
                value={replacementQty}
                onChange={(e) => setReplacementQty(e.target.value)}
                sx={{ width: { xs: "100%", sm: 130 } }}
              />
              <Button
                variant="outlined"
                disabled={!replacementVariant || Number(replacementQty) <= 0}
                onClick={addReplacement}
              >
                Add
              </Button>
            </Stack>
            {replacements.map((r) => (
              <Stack
                key={r.variant_id}
                direction="row"
                justifyContent="space-between"
                alignItems="center"
              >
                <span>
                  {r.name} × {quantity(r.quantity)}
                </span>
                <Button
                  color="error"
                  onClick={() =>
                    setReplacements(
                      replacements.filter((x) => x.variant_id !== r.variant_id),
                    )
                  }
                >
                  Remove
                </Button>
              </Stack>
            ))}
            <TextField
              select
              label={
                replacements.length
                  ? "Balance payment / refund method"
                  : "Refund method"
              }
              value={method}
              onChange={(e) =>
                setMethod(e.target.value as "cash" | "card" | "upi")
              }
            >
              <MenuItem value="cash">Cash</MenuItem>
              <MenuItem value="card">Card</MenuItem>
              <MenuItem value="upi">UPI</MenuItem>
            </TextField>
            <TextField
              label="Return or exchange reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              multiline
              minRows={2}
            />
            {quote && quote.fingerprint !== fingerprint && (
              <Alert severity="warning">
                The exchange details changed. Review the totals again before
                completing.
              </Alert>
            )}
            {quote && quote.fingerprint === fingerprint && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <div className="total-line">
                  <span>Return credit</span>
                  <strong>{money(quote.return_total)}</strong>
                </div>
                <div className="total-line">
                  <span>New items total</span>
                  <strong>{money(quote.replacement_total)}</strong>
                </div>
                {Number(quote.amount_due) > 0 ? (
                  <Alert severity="info">
                    Customer must pay {money(quote.amount_due)} by{" "}
                    {method.toUpperCase()}.
                  </Alert>
                ) : Number(quote.refund_due) > 0 ? (
                  <Alert severity="warning">
                    Return {money(quote.refund_due)} to the customer by{" "}
                    {method.toUpperCase()}.
                  </Alert>
                ) : (
                  <Alert severity="success">
                    Even exchange — no payment or refund.
                  </Alert>
                )}
                {method === "cash" && Number(quote.amount_due) > 0 && (
                  <TextField
                    fullWidth
                    type="number"
                    label="Actual cash received"
                    value={cashReceived}
                    onChange={(e) => setCashReceived(e.target.value)}
                    inputProps={{ min: 0, step: 0.01 }}
                    error={
                      cashReceived !== "" &&
                      Number(cashReceived) < Number(quote.amount_due)
                    }
                    helperText={
                      cashReceived === ""
                        ? "Required before completion"
                        : Number(cashReceived) < Number(quote.amount_due)
                          ? `Cash is ${money(Number(quote.amount_due) - Number(cashReceived))} short`
                          : "The backend will calculate and record the change"
                    }
                    sx={{ mt: 2 }}
                  />
                )}
              </Paper>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelected(null)}>Cancel</Button>
          <Button
            disabled={
              busy ||
              !item ||
              Number(returnQty) <= 0 ||
              reason.trim().length < 3
            }
            onClick={() => void review()}
          >
            Review totals
          </Button>
          <Button
            variant="contained"
            disabled={
              busy ||
              !quote ||
              quote.fingerprint !== fingerprint ||
              (method === "cash" &&
                Number(quote.amount_due) > 0 &&
                (cashReceived === "" ||
                  Number(cashReceived) < Number(quote.amount_due)))
            }
            onClick={() => void process()}
          >
            {replacements.length
              ? "Complete exchange"
              : "Complete return & refund"}
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={!!result}
        onClose={() => setResult(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>
          {result?.kind === "exchange" ? "Exchange receipt" : "Return receipt"}
        </DialogTitle>
        <DialogContent>
          {result && (
            <div className="print-receipt">
              <h2>CHINNU</h2>
              <p>
                {result.number}
                <br />
                Original: {result.original_receipt}
                <br />
                {result.customer_name} · {result.customer_code}
                <br />
                {date(result.created_at)}
              </p>
              <Divider />
              <Typography variant="subtitle2">RETURNED</Typography>
              {result.returned_items.map((x, i) => (
                <div className="total-line" key={i}>
                  <span>
                    {x.name} × {quantity(x.quantity)} {x.unit}
                    <br />
                    <small>{x.condition}</small>
                  </span>
                  <strong>{money(x.line_total)}</strong>
                </div>
              ))}
              {result.replacement_items.length > 0 && (
                <>
                  <Divider />
                  <Typography variant="subtitle2">NEW ITEMS</Typography>
                  {result.replacement_items.map((x, i) => (
                    <div className="total-line" key={i}>
                      <span>
                        {x.name} × {quantity(x.quantity)} {x.unit}
                      </span>
                      <strong>{money(x.line_total)}</strong>
                    </div>
                  ))}
                </>
              )}
              <Divider />
              <div className="total-line">
                <span>Return credit</span>
                <strong>{money(result.return_total)}</strong>
              </div>
              <div className="total-line">
                <span>New items total</span>
                <strong>{money(result.replacement_total)}</strong>
              </div>
              <div className="total-line">
                <strong>
                  {Number(result.amount_due) > 0
                    ? "Customer paid"
                    : Number(result.refund_due) > 0
                      ? "Refunded"
                      : "Even exchange"}
                </strong>
                <strong>
                  {money(
                    Number(result.amount_due) > 0
                      ? result.amount_due
                      : result.refund_due,
                  )}
                </strong>
              </div>
              {result.settlement_method === "cash" &&
                result.amount_tendered && (
                  <>
                    <div className="total-line">
                      <span>Cash received</span>
                      <strong>{money(result.amount_tendered)}</strong>
                    </div>
                    <div className="total-line">
                      <span>Balance returned</span>
                      <strong>{money(result.change_due)}</strong>
                    </div>
                  </>
                )}
              <p>
                Settlement: {result.settlement_method.toUpperCase()}
                <br />
                {result.reason}
              </p>
            </div>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResult(null)}>Close</Button>
          <Button variant="contained" onClick={() => window.print()}>
            Print
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

type Transfer = {
  id: number;
  source_id: number;
  target_id: number;
  source: string;
  target: string;
  name: string;
  quantity: string;
  received: string;
  status: string;
};
function Transfers({
  branch,
  branches,
}: {
  branch: number;
  branches: Branch[];
}) {
  const { user, catalogue, notify } = useApp(),
    qc = useQueryClient();
  const [open, setOpen] = useState(false),
    [target, setTarget] = useState(""),
    [variant, setVariant] = useState(""),
    [qty, setQty] = useState("1"),
    [busy, setBusy] = useState(false),
    [receiving, setReceiving] = useState<Transfer | null>(null),
    [receivedQty, setReceivedQty] = useState("1");
  const query = useQuery({
    queryKey: ["transfers", branch],
    queryFn: () =>
      api<Transfer[]>(branch ? `/transfers?branch_id=${branch}` : "/transfers"),
  });
  const options = catalogue.flatMap((p) =>
    p.variants.map((v) => ({ id: v.id, name: p.name + " · " + v.label })),
  );
  async function dispatch() {
    if (!branch) {
      notify("Select a specific branch before dispatching stock.");
      return;
    }
    setBusy(true);
    try {
      await post(
        "/transfers",
        {
          source_id: branch,
          target_id: Number(target),
          variant_id: Number(variant),
          quantity: qty,
        },
        key(),
      );
      setOpen(false);
      await qc.invalidateQueries();
      notify("Stock dispatched and marked in transit.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function receive() {
    if (!receiving) return;
    setBusy(true);
    try {
      await post(
        `/transfers/${receiving.id}/receive`,
        { quantity: receivedQty },
        key(),
      );
      setReceiving(null);
      await qc.invalidateQueries();
      notify("Received quantity added to destination stock.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        title="Stock transfers"
        subtitle="Dispatch from the working branch. Receive at the destination; stock stays in transit until then."
        action={
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => setOpen(true)}
          >
            Dispatch transfer
          </Button>
        }
      />
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}
      <DataTable
        rows={query.data || []}
        columns={[
          { label: "Transfer", value: (t) => `TR-${t.id}` },
          { label: "Route", value: (t) => `${t.source} → ${t.target}` },
          { label: "Product", value: (t) => t.name },
          { label: "Sent", value: (t) => quantity(t.quantity) },
          { label: "Received", value: (t) => quantity(t.received) },
          { label: "Status", value: (t) => <Status value={t.status} /> },
          {
            label: "Action",
            value: (t) =>
              t.status !== "received" &&
              (user?.role === "admin" || t.target_id === user?.branch_id) ? (
                <Button
                  onClick={() => {
                    setReceiving(t);
                    setReceivedQty(
                      String(Number(t.quantity) - Number(t.received)),
                    );
                  }}
                >
                  Receive
                </Button>
              ) : null,
          },
        ]}
      />
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Dispatch stock</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="Source"
              value={branches.find((b) => b.id === branch)?.name || ""}
              disabled
            />
            <TextField
              select
              label="Destination"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              {branches
                .filter((b) => b.id !== branch)
                .map((b) => (
                  <MenuItem key={b.id} value={b.id}>
                    {b.name}
                  </MenuItem>
                ))}
            </TextField>
            <TextField
              select
              label="Product variant"
              value={variant}
              onChange={(e) => setVariant(e.target.value)}
            >
              {options.map((v) => (
                <MenuItem key={v.id} value={v.id}>
                  {v.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              type="number"
              label="Quantity"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              inputProps={{ min: 0.001, step: 0.001 }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button
            disabled={busy || !target || !variant || Number(qty) <= 0}
            onClick={() => void dispatch()}
            variant="contained"
          >
            Dispatch
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog open={!!receiving} onClose={() => setReceiving(null)}>
        <DialogTitle>Receive transfer TR-{receiving?.id}</DialogTitle>
        <DialogContent>
          <Typography sx={{ mb: 2 }}>
            Enter the quantity physically received. Partial receipts keep the
            rest in transit.
          </Typography>
          <TextField
            label="Received quantity"
            type="number"
            value={receivedQty}
            onChange={(e) => setReceivedQty(e.target.value)}
            inputProps={{ min: 0.001, step: 0.001 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReceiving(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={busy || Number(receivedQty) <= 0}
            onClick={() => void receive()}
          >
            Confirm receipt
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

type Supplier = { id: number; name: string; phone: string; address: string };
type Purchase = {
  id: number;
  branch_name: string;
  name: string;
  supplier: string;
  quantity: string;
  received: string;
  unit_cost: string;
  selling_price: string;
  profit_per_unit: string;
  margin_percent: string;
  status: string;
};
function Purchases({ branch }: { branch: number }) {
  const { user, catalogue, notify } = useApp(),
    qc = useQueryClient();
  const [open, setOpen] = useState(false),
    [supplierOpen, setSupplierOpen] = useState(false),
    [supplier, setSupplier] = useState(""),
    [variant, setVariant] = useState(""),
    [qty, setQty] = useState("10"),
    [cost, setCost] = useState("1"),
    [busy, setBusy] = useState(false),
    [receive, setReceive] = useState<Purchase | null>(null),
    [received, setReceived] = useState("1"),
    [receivedCost, setReceivedCost] = useState("1"),
    [name, setName] = useState(""),
    [phone, setPhone] = useState("");
  const suppliers = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => api<Supplier[]>("/suppliers"),
  });
  const query = useQuery({
    queryKey: ["purchases", branch],
    queryFn: () =>
      api<Purchase[]>(branch ? `/purchases?branch_id=${branch}` : "/purchases"),
  });
  async function save() {
    if (!branch) {
      notify("Select a specific branch before creating a purchase.");
      return;
    }
    setBusy(true);
    try {
      await post(
        "/purchases",
        {
          branch_id: branch,
          supplier_id: Number(supplier),
          variant_id: Number(variant),
          quantity: qty,
          unit_cost: cost,
        },
        key(),
      );
      setOpen(false);
      await qc.invalidateQueries();
      notify("Purchase order created. Stock changes only when received.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function saveSupplier() {
    setBusy(true);
    try {
      await post("/suppliers", { name, phone, address: "" });
      setSupplierOpen(false);
      setName("");
      await qc.invalidateQueries();
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function accept() {
    if (!receive) return;
    setBusy(true);
    try {
      await post(
        `/purchases/${receive.id}/receive`,
        { quantity: received, unit_cost: receivedCost },
        key(),
      );
      setReceive(null);
      await qc.invalidateQueries();
      notify(
        "Accepted quantity and buying price recorded. Branch inventory updated.",
      );
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        title="Purchasing & goods receiving"
        subtitle="Record buying prices, receive goods, and compare cost with the current selling price."
        action={
          <Stack direction="row" spacing={1}>
            {user?.role === "admin" && (
              <Button variant="outlined" onClick={() => setSupplierOpen(true)}>
                Add supplier
              </Button>
            )}
            {user?.role !== "inventory" && (
              <Button variant="contained" onClick={() => setOpen(true)}>
                New purchase
              </Button>
            )}
          </Stack>
        }
      />
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}
      <DataTable
        rows={query.data || []}
        columns={[
          { label: "Purchase", value: (p) => `PO-${p.id}` },
          { label: "Supplier", value: (p) => p.supplier },
          { label: "Product", value: (p) => p.name },
          { label: "Ordered", value: (p) => quantity(p.quantity) },
          { label: "Received", value: (p) => quantity(p.received) },
          { label: "Buying price", value: (p) => money(p.unit_cost) },
          { label: "Selling price", value: (p) => money(p.selling_price) },
          {
            label: "Profit / unit",
            value: (p) => (
              <>
                <strong>{money(p.profit_per_unit)}</strong>
                <Typography variant="caption" display="block">
                  {p.margin_percent}% margin
                </Typography>
              </>
            ),
          },
          { label: "Status", value: (p) => <Status value={p.status} /> },
          {
            label: "Action",
            value: (p) =>
              p.status !== "received" ? (
                <Button
                  onClick={() => {
                    setReceive(p);
                    setReceived(
                      String(Number(p.quantity) - Number(p.received)),
                    );
                    setReceivedCost(p.unit_cost);
                  }}
                >
                  Receive
                </Button>
              ) : null,
          },
        ]}
      />
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Create purchase order</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              select
              label="Supplier"
              value={supplier}
              onChange={(e) => setSupplier(e.target.value)}
            >
              {suppliers.data?.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Product variant"
              value={variant}
              onChange={(e) => setVariant(e.target.value)}
            >
              {catalogue.flatMap((p) =>
                p.variants.map((v) => (
                  <MenuItem key={v.id} value={v.id}>
                    {p.name} · {v.label}
                  </MenuItem>
                )),
              )}
            </TextField>
            <TextField
              label="Quantity"
              type="number"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              inputProps={{ min: 0.001, step: 0.001 }}
            />
            <TextField
              label="Cost per selling unit"
              type="number"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              inputProps={{ min: 0.01, step: 0.01 }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={
              busy ||
              !supplier ||
              !variant ||
              Number(qty) <= 0 ||
              Number(cost) <= 0
            }
            onClick={() => void save()}
          >
            Create purchase
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={supplierOpen}
        onClose={() => setSupplierOpen(false)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>Add supplier</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="Supplier name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <TextField
              label="Phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSupplierOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={busy || name.length < 2}
            onClick={() => void saveSupplier()}
          >
            Add supplier
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog open={!!receive} onClose={() => setReceive(null)}>
        <DialogTitle>Receive PO-{receive?.id}</DialogTitle>
        <DialogContent>
          <Stack spacing={2}>
            <Alert severity="info">
              Receive accepted sellable goods only. Record damaged goods
              separately through inventory.
            </Alert>
            <TextField
              type="number"
              label="Accepted quantity"
              value={received}
              onChange={(e) => setReceived(e.target.value)}
              inputProps={{ min: 0.001, step: 0.001 }}
            />
            <TextField
              type="number"
              label="Actual buying price per unit"
              value={receivedCost}
              onChange={(e) => setReceivedCost(e.target.value)}
              inputProps={{ min: 0.01, step: 0.01 }}
              helperText={
                receive && Number(receive.received) > 0
                  ? "Fixed after the first partial receipt"
                  : "Confirm the supplier invoice price"
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReceive(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={
              busy || Number(received) <= 0 || Number(receivedCost) <= 0
            }
            onClick={() => void accept()}
          >
            Receive goods
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

type DraftVariant = {
  id?: number;
  sku: string;
  label: string;
  unit: string;
  price: string;
  min_qty: string;
  step: string;
  max_qty: string;
};
const newVariant = (): DraftVariant => ({
  sku: "",
  label: "",
  unit: "pack",
  price: "",
  min_qty: "1",
  step: "1",
  max_qty: "100",
});
function Products() {
  const { catalogue, notify } = useApp(),
    qc = useQueryClient();
  const categories = useQuery({
    queryKey: ["product-categories"],
    queryFn: () => api<string[]>("/admin/product-categories"),
  });
  const [open, setOpen] = useState(false),
    [editingProduct, setEditingProduct] = useState<Product | null>(null),
    [name, setName] = useState(""),
    [category, setCategory] = useState("Rice"),
    [description, setDescription] = useState(""),
    [tone, setTone] = useState("sage"),
    [variants, setVariants] = useState<DraftVariant[]>([newVariant()]),
    [busy, setBusy] = useState(false),
    [priceTarget, setPriceTarget] = useState<{
      id: number;
      name: string;
    } | null>(null),
    [price, setPrice] = useState("");
  const confirmation = useConfirmDialog();
  function update(i: number, k: keyof DraftVariant, value: string) {
    setVariants((current) =>
      current.map((v, index) => (index === i ? { ...v, [k]: value } : v)),
    );
  }
  async function create() {
    setBusy(true);
    try {
      if (editingProduct) await api(`/admin/products/${editingProduct.id}`, {
        method: "PUT",
        body: JSON.stringify({name, category, description, tone, variants}),
      });
      else await post("/admin/products", {
        name,
        category,
        description,
        tone,
        variants,
      });
      setOpen(false);
      setName("");
      setDescription("");
      setVariants([newVariant()]);
      await qc.invalidateQueries();
      notify(editingProduct ? "Product updated." : "Product created. Receive stock before selling.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function updatePrice() {
    if (!priceTarget) return;
    setBusy(true);
    try {
      await api(`/admin/variants/${priceTarget.id}/price`, {
        method: "PATCH",
        body: JSON.stringify({ price }),
      });
      setPriceTarget(null);
      await qc.invalidateQueries();
      notify("Central price updated for all branches.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function archive(p: Product) {
    if (
      !(await confirmation.ask(
        `Archive ${p.name}? Existing order and sale history will be retained.`,
        { title: "Archive product", confirmLabel: "Archive", danger: true },
      ))
    )
      return;
    try {
      await post(`/admin/products/${p.id}/archive`);
      await qc.invalidateQueries();
    } catch (err) {
      notify((err as Error).message);
    }
  }
  return (
    <>
      <Heading
        title="Product catalogue"
        subtitle="One shared price list. Configure sealed packs, loose goods, or both per product."
        action={
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => {
              setEditingProduct(null);
              setName(""); setCategory(""); setDescription(""); setTone("sage");
              setVariants([newVariant()]); setOpen(true);
            }}
          >
            Add product
          </Button>
        }
      />
      <DataTable
        rows={catalogue}
        columns={[
          {
            label: "Product",
            value: (p) => (
              <>
                <strong>{p.name}</strong>
                <Typography variant="caption" display="block">
                  {p.description}
                </Typography>
              </>
            ),
          },
          { label: "Category", value: (p) => p.category },
          {
            label: "Variants & prices",
            value: (p) => (
              <Stack spacing={0.5}>
                {p.variants.map((v) => (
                  <Stack
                    key={v.id}
                    direction="row"
                    spacing={1}
                    alignItems="center"
                  >
                    <span>
                      {v.label} · {money(v.price)}/{v.unit}
                    </span>
                    <Button
                      size="small"
                      onClick={() => {
                        setPriceTarget({
                          id: v.id,
                          name: p.name + " · " + v.label,
                        });
                        setPrice(v.price);
                      }}
                    >
                      Edit price
                    </Button>
                  </Stack>
                ))}
              </Stack>
            ),
          },
          {
            label: "Action",
            value: (p) => (
              <Stack direction="row" spacing={1}>
              <Button onClick={() => {
                setEditingProduct(p); setName(p.name); setCategory(p.category);
                setDescription(p.description); setTone(p.tone); setOpen(true);
                setVariants(p.variants.map(v => ({...v})));
              }}>Edit product</Button>
              <Button color="error" onClick={() => void archive(p)}>
                Archive
              </Button>
              </Stack>
            ),
          },
        ]}
      />
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>{editingProduct ? "Edit product" : "Add product and selling options"}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1, "& .MuiFormLabel-asterisk": { color: "error.main" } }}>
            <Typography variant="body2" color="text.secondary">
              Fields marked with * are required. Suggested values are already filled in where available.
            </Typography>
            <TextField
              label="Product name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <Stack direction="row" spacing={2}>
              <Autocomplete
                freeSolo
                fullWidth
                options={categories.data || []}
                inputValue={category}
                onInputChange={(_, value) => setCategory(value)}
                onChange={(_, value) => setCategory(value || "")}
                loading={categories.isLoading}
                renderInput={(params) => <TextField {...params} label="Category" required
                  helperText={categories.isError ? "Could not load categories. You can still enter a new category." : "Select an existing category or type a new one."} />}
              />
              <TextField
                select
                label="Packaging colour"
                required
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                fullWidth
              >
                {["sage", "gold", "rose", "clay"].map((t) => (
                  <MenuItem value={t} key={t}>
                    {t}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
            <TextField
              label="Description (optional)"
              multiline
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <>
            <Alert severity="info">
              Sealed packs use whole quantities. Loose goods use kg or litres.
              Each selling option has its own stock; pack opening does not
              automatically convert stock.
            </Alert>
            {variants.map((v, i) => (
              <Paper key={i} variant="outlined" sx={{ p: 2 }}>
                <Stack spacing={2}>
                  <Stack direction="row" spacing={2}>
                    <TextField
                      fullWidth
                      label="Unique SKU / barcode"
                      required
                      value={v.sku}
                      onChange={(e) => update(i, "sku", e.target.value)}
                    />
                    <TextField
                      fullWidth
                      label="Option label (e.g. 1 kg sealed pack)"
                      required
                      value={v.label}
                      onChange={(e) => update(i, "label", e.target.value)}
                    />
                  </Stack>
                  <Stack direction="row" spacing={2}>
                    <TextField
                      select
                      fullWidth
                      label="Selling unit"
                      required
                      value={v.unit}
                      onChange={(e) => {
                        const value = e.target.value;
                        setVariants((current) =>
                          current.map((x, index) =>
                            index === i
                              ? {
                                  ...x,
                                  unit: value,
                                  min_qty:
                                    value === "kg" || value === "litre"
                                      ? "0.25"
                                      : "1",
                                  step:
                                    value === "kg" || value === "litre"
                                      ? "0.25"
                                      : "1",
                                }
                              : x,
                          ),
                        );
                      }}
                    >
                      {["pack", "piece", "kg", "litre"].map((u) => (
                        <MenuItem key={u} value={u}>
                          {u}
                        </MenuItem>
                      ))}
                    </TextField>
                    <TextField
                      fullWidth
                      label="Price per unit"
                      required
                      type="number"
                      value={v.price}
                      onChange={(e) => update(i, "price", e.target.value)}
                    />
                  </Stack>
                  <Stack direction="row" spacing={2}>
                    {(["min_qty", "step", "max_qty"] as const).map((k) => (
                      <TextField
                        key={k}
                        required
                        label={
                          {
                            min_qty: "Minimum qty",
                            step: "Quantity increment",
                            max_qty: "Maximum qty",
                          }[k]
                        }
                        type="number"
                        value={v[k]}
                        onChange={(e) => update(i, k, e.target.value)}
                        inputProps={{ min: 0.001, step: 0.001 }}
                      />
                    ))}
                  </Stack>
                  {variants.length > 1 && !v.id && (
                    <Button
                      color="error"
                      onClick={() =>
                        setVariants(variants.filter((_, index) => index !== i))
                      }
                    >
                      Remove option
                    </Button>
                  )}
                </Stack>
              </Paper>
            ))}
            <Button onClick={() => setVariants([...variants, newVariant()])}>
              Add another pack or loose option
            </Button>
            </>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={
              busy ||
              name.length < 2 ||
              category.trim().length < 2 ||
              variants.some((v) => !v.sku || !v.label || Number(v.price) <= 0)
            }
            onClick={() => void create()}
          >
            {editingProduct ? "Save changes" : "Create product"}
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog open={!!priceTarget} onClose={() => setPriceTarget(null)}>
        <DialogTitle>Update central price</DialogTitle>
        <DialogContent>
          <Typography sx={{ mb: 2 }}>{priceTarget?.name}</Typography>
          <TextField
            label="Price"
            type="number"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            inputProps={{ min: 0.01, step: 0.01 }}
          />
          <Typography variant="caption" display="block" sx={{ mt: 2 }}>
            Existing orders and receipts retain their original prices.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPriceTarget(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={busy || Number(price) <= 0}
            onClick={() => void updatePrice()}
          >
            Update all branches
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

const emptyBranch = {
  name: "",
  address: "",
  latitude: "",
  longitude: "",
  radius_km: "12",
  delivery_fee: "30",
  hours: "09:00–21:00",
  accepting_orders: true,
  active: true,
};
function Branches({ branches }: { branches: Branch[] }) {
  const [deliverySlabs, setDeliverySlabs] = useState<{up_to_km:string;fee:string}[]>([]);
  const { notify } = useApp(),
    qc = useQueryClient();
  const [open, setOpen] = useState(false),
    [editing, setEditing] = useState<number | null>(null),
    [form, setForm] = useState(emptyBranch),
    [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    try {
      const data = {
        ...form,
        delivery_slabs: deliverySlabs,
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
      };
      if (editing)
        await api(`/admin/branches/${editing}`, {
          method: "PUT",
          body: JSON.stringify(data),
        });
      else await post("/admin/branches", data);
      setOpen(false);
      await qc.invalidateQueries();
      notify("Branch saved.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function edit(b: Branch) {
    setDeliverySlabs(b.delivery_slabs || []);
    setEditing(b.id);
    setForm({
      name: b.name,
      address: b.address,
      latitude: String(b.latitude),
      longitude: String(b.longitude),
      radius_km: String(b.radius_km),
      delivery_fee: String(b.delivery_fee),
      hours: b.hours,
      accepting_orders: b.accepting_orders,
      active: b.active,
    });
    setOpen(true);
  }
  return (
    <>
      <Heading
        title="Branch management"
        subtitle="Configure locations, delivery coverage, fees, and online order availability."
        action={
          <Button
            variant="contained"
            onClick={() => {
              setEditing(null);
              setForm(emptyBranch);
              setDeliverySlabs([]);
              setOpen(true);
            }}
          >
            Add branch
          </Button>
        }
      />
      <div className="branch-grid branch-management-grid">
        {branches.map((b) => (
          <Paper key={b.id} variant="outlined" className="branch-management-card">
            <div className="branch-card-header">
              <span className="branch-card-icon"><StorefrontOutlined /></span>
              <Chip size="small" label={!b.active ? "Inactive" : b.accepting_orders ? "Accepting orders" : "Orders paused"}
                color={!b.active ? "default" : b.accepting_orders ? "success" : "warning"} variant="outlined" />
            </div>
            <Typography variant="h6">{b.name}</Typography>
            <Typography className="branch-card-address" color="text.secondary">
              {b.address}
            </Typography>
            <dl className="branch-card-details">
              <div><dt>Opening hours</dt><dd>{b.hours}</dd></div>
              <div><dt>Delivery radius</dt><dd>{Number(b.radius_km)} km</dd></div>
              <div><dt>Delivery pricing</dt><dd>{b.delivery_slabs?.length ? `${b.delivery_slabs.length} distance slabs` : money(b.delivery_fee)}</dd></div>
            </dl>
            <div className="branch-card-footer">
              <Button size="small" component="a" href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${b.latitude},${b.longitude}`)}`} target="_blank" rel="noopener noreferrer">View location ↗</Button>
              <Button variant="outlined" onClick={() => edit(b)}>
                Edit branch
              </Button>
            </div>
          </Paper>
        ))}
      </div>
      {!branches.length && <Alert severity="info">No branches yet. Add your first branch to configure its location and delivery coverage.</Alert>}
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>{editing ? "Edit branch" : "Add branch"}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {(
              [
                "name",
                "address",
                "latitude",
                "longitude",
                "radius_km",
                "delivery_fee",
                "hours",
              ] as const
            ).map((k) => (
              <TextField
                key={k}
                label={
                  {
                    name: "Branch name",
                    address: "Branch address",
                    latitude: "Latitude",
                    longitude: "Longitude",
                    radius_km: "Delivery radius in km",
                    delivery_fee: "Flat delivery charge (used only without distance slabs)",
                    hours: "Displayed operating hours",
                  }[k]
                }
                value={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              />
            ))}
            <Paper variant="outlined" sx={{p:2}}>
              <Typography variant="subtitle1" fontWeight={700}>Distance-based delivery charges</Typography>
              <Typography variant="body2" color="text.secondary" sx={{mb:2}}>
                Add distance limits in increasing order. Each price applies above the previous limit, up to and including this limit. The first starts at 0 km. The final limit must match the delivery radius. Distances are straight-line estimates, not driving distances.
              </Typography>
              <Stack spacing={2}>
                {deliverySlabs.map((slab,i) => <Stack key={i} direction={{xs:"column",sm:"row"}} spacing={1} alignItems={{sm:"center"}}>
                  <TextField required type="number" label={i===0 ? "0 km up to (km)" : `Over ${deliverySlabs[i-1].up_to_km || "previous"} km up to (km)`}
                    value={slab.up_to_km} inputProps={{min:0.01,max:500,step:0.01}}
                    onChange={e=>setDeliverySlabs(deliverySlabs.map((s,index)=>index===i?{...s,up_to_km:e.target.value}:s))}/>
                  <TextField required type="number" label="Delivery charge (₹)" value={slab.fee} inputProps={{min:0,max:10000,step:0.01}}
                    onChange={e=>setDeliverySlabs(deliverySlabs.map((s,index)=>index===i?{...s,fee:e.target.value}:s))}/>
                  <Button color="error" onClick={()=>setDeliverySlabs(deliverySlabs.filter((_,index)=>index!==i))}>Remove</Button>
                </Stack>)}
                <Button variant="outlined" disabled={deliverySlabs.length>=30} onClick={()=>setDeliverySlabs([...deliverySlabs,{up_to_km:"",fee:""}])}>Add distance slab</Button>
                {!deliverySlabs.length && <Typography variant="caption">No slabs: the flat delivery charge applies within the branch radius.</Typography>}
                <Typography variant="caption">Outside the delivery radius, a manager must still approve the order and enter a manual delivery charge.</Typography>
              </Stack>
            </Paper>
            <TextField
              select
              label="Online orders"
              value={String(form.accepting_orders)}
              onChange={(e) =>
                setForm({
                  ...form,
                  accepting_orders: e.target.value === "true",
                })
              }
            >
              <MenuItem value="true">Accepting orders</MenuItem>
              <MenuItem value="false">Paused</MenuItem>
            </TextField>
            <Typography variant="caption">
              Hours are displayed to customers. Use the accepting orders control
              to open or pause checkout.
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={
              busy ||
              !form.name ||
              !form.address ||
              !form.latitude ||
              !form.longitude
            }
            onClick={() => void save()}
          >
            Save branch
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

function Users({ branches, selectedBranch }: { branches: Branch[]; selectedBranch: number }) {
  const { user, notify } = useApp(),
    qc = useQueryClient();
  const [open, setOpen] = useState(false),
    [editing, setEditing] = useState<User | null>(null),
    [name, setName] = useState(""),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [role, setRole] = useState("cashier"),
    [branch, setBranch] = useState(""),
    [passwordOpen, setPasswordOpen] = useState(false),
    [currentPassword, setCurrentPassword] = useState(""),
    [newPassword, setNewPassword] = useState(""),
    [confirmPassword, setConfirmPassword] = useState(""),
    [busy, setBusy] = useState(false);
  const confirmation = useConfirmDialog();
  const query = useQuery({
    queryKey: ["users", selectedBranch],
    queryFn: () => api<User[]>("/admin/users" + (selectedBranch ? `?branch_id=${selectedBranch}` : "")),
  });
  function add() {
    setEditing(null);
    setName("");
    setEmail("");
    setPassword("");
    setRole("cashier");
    setBranch(selectedBranch ? String(selectedBranch) : "");
    setOpen(true);
  }
  function edit(u: User) {
    setEditing(u);
    setName(u.name);
    setEmail(u.email || "");
    setPassword("");
    setRole(u.role);
    setBranch(String(u.branch_id || ""));
    setOpen(true);
  }
  async function save() {
    setBusy(true);
    try {
      if (editing)
        await api(`/admin/users/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify({
            name,
            email,
            role,
            branch_id: Number(branch),
            password: password || null,
          }),
        });
      else
        await post("/admin/users", {
          name,
          email,
          password,
          role,
          branch_id: Number(branch),
        });
      setOpen(false);
      setPassword("");
      await qc.invalidateQueries();
      notify(editing ? "Staff credentials updated." : "Staff account created.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function changeMyPassword() {
    setBusy(true);
    try {
      await api("/admin/password", {
        method: "PUT",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setPasswordOpen(false);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      notify(
        "Your password has been changed. Other administrator sessions were signed out.",
      );
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function toggle(u: User) {
    if (
      !(await confirmation.ask(
        `${u.active ? "Disable" : "Enable"} ${u.name}'s account?`,
        {
          title: `${u.active ? "Disable" : "Enable"} account`,
          confirmLabel: u.active ? "Disable" : "Enable",
          danger: u.active,
        },
      ))
    )
      return;
    try {
      await post(`/admin/users/${u.id}/toggle`);
      await qc.invalidateQueries();
    } catch (err) {
      notify((err as Error).message);
    }
  }
  return (
    <>
      <Heading
        title="People & access"
        subtitle="Every staff account has a clear role and one assigned branch."
        action={
          <Button variant="contained" onClick={add}>
            Add staff member
          </Button>
        }
      />
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}
      <DataTable
        rows={query.data || []}
        columns={[
          { label: "Name", value: (u) => <strong>{u.name}</strong> },
          { label: "Email", value: (u) => u.email },
          { label: "Role", value: (u) => u.role },
          {
            label: "Branch",
            value: (u) =>
              branches.find((b) => b.id === u.branch_id)?.name || "—",
          },
          {
            label: "Status",
            value: (u) => <Status value={u.active ? "active" : "inactive"} />,
          },
          {
            label: "Action",
            value: (u) =>
              u.role === "admin" && u.id === user?.id ? (
                <Button onClick={() => setPasswordOpen(true)}>
                  Change my password
                </Button>
              ) : u.role !== "admin" ? (
                <Stack direction="row" spacing={1}>
                  <Button onClick={() => edit(u)}>Edit credentials</Button>
                  <Button onClick={() => void toggle(u)}>
                    {u.active ? "Disable" : "Enable"}
                  </Button>
                </Stack>
              ) : null,
          },
        ]}
      />
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>
          {editing ? "Edit staff credentials" : "Add staff member"}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <TextField
              label={
                editing
                  ? "New password (leave blank to keep current)"
                  : "Initial password (10+ characters)"
              }
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              helperText={
                editing
                  ? "Entering a new password signs this employee out of existing sessions."
                  : ""
              }
            />
            <TextField
              select
              label="Role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              {["manager", "cashier", "inventory", "delivery"].map((r) => (
                <MenuItem key={r} value={r}>
                  {r}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Assigned branch"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
            >
              {branches.map((b) => (
                <MenuItem key={b.id} value={b.id}>
                  {b.name}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={
              busy ||
              name.trim().length < 2 ||
              !email ||
              (!editing && password.length < 10) ||
              (editing && password.length > 0 && password.length < 10) ||
              !branch
            }
            onClick={() => void save()}
          >
            {editing ? "Save changes" : "Create account"}
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={passwordOpen}
        onClose={() => setPasswordOpen(false)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>Change my password</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              autoFocus
              type="password"
              label="Current password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
            <TextField
              type="password"
              label="New password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              helperText="Use at least 10 characters."
            />
            <TextField
              type="password"
              label="Confirm new password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              error={
                confirmPassword.length > 0 && confirmPassword !== newPassword
              }
              helperText={
                confirmPassword.length > 0 && confirmPassword !== newPassword
                  ? "Passwords do not match."
                  : "Other administrator sessions will be signed out."
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPasswordOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={
              busy ||
              !currentPassword ||
              newPassword.length < 10 ||
              newPassword !== confirmPassword
            }
            onClick={() => void changeMyPassword()}
          >
            Change password
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

type CustomerRecord = {
  id: string;
  name: string;
  mobile: string;
  email: string | null;
  public_code: string;
  source: "online" | "store" | "linked";
  visits: number;
  pos_purchases: number;
  online_orders: number;
  lifetime_value: string;
  returned_value: string;
  exchange_count: number;
  last_visit: string | null;
  preferred_payment: string | null;
};
type CustomerDetail = CustomerRecord & {
  sales: Sale[];
  orders: Order[];
  returns_exchanges: ReturnExchangeResult[];
};
function Customers() {
  const [draft, setDraft] = useState(""),
    [search, setSearch] = useState(""),
    [selected, setSelected] = useState<string | null>(null),
    [saleBill, setSaleBill] = useState<Sale | null>(null),
    [exchangeBill, setExchangeBill] = useState<ReturnExchangeResult | null>(
      null,
    );
  const query = useQuery({
    queryKey: ["admin-customers", search],
    queryFn: () =>
      api<CustomerRecord[]>(
        `/admin/customers${search ? `?q=${encodeURIComponent(search)}` : ""}`,
      ),
  });
  const detail = useQuery({
    queryKey: ["admin-customer", selected],
    queryFn: () => api<CustomerDetail>(`/admin/customers/${selected}`),
    enabled: selected !== null,
  });
  const customer = detail.data;
  return (
    <>
      <Heading
        title="Customer directory"
        subtitle="Online accounts and store customers are securely linked when their mobile numbers match."
      />
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <TextField
            fullWidth
            label="Search name, mobile number, email, or customer code"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") setSearch(draft.trim());
            }}
          />
          <Button variant="contained" onClick={() => setSearch(draft.trim())}>
            Search
          </Button>
          {search && (
            <Button
              color="inherit"
              onClick={() => {
                setDraft("");
                setSearch("");
              }}
            >
              Clear
            </Button>
          )}
        </Stack>
      </Paper>
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}
      <DataTable
        rows={query.data || []}
        columns={[
          {
            label: "Customer",
            value: (c) => (
              <>
                <strong>{c.name}</strong>
                <Typography variant="caption" display="block">
                  {c.public_code} ·{" "}
                  {c.source === "linked"
                    ? "Online + store"
                    : c.source === "online"
                      ? "Online"
                      : "Store"}
                </Typography>
              </>
            ),
          },
          {
            label: "Mobile",
            value: (c) => (
              <>
                {c.mobile}
                <Typography variant="caption" display="block">
                  {c.email || "No email"}
                </Typography>
              </>
            ),
          },
          { label: "Store purchases", value: (c) => c.pos_purchases },
          { label: "Online orders", value: (c) => c.online_orders },
          {
            label: "Lifetime value",
            value: (c) => <strong>{money(c.lifetime_value)}</strong>,
          },
          {
            label: "Last activity",
            value: (c) => (c.last_visit ? date(c.last_visit) : "No purchases"),
          },
          {
            label: "Action",
            value: (c) => (
              <Button onClick={() => setSelected(c.id)}>View data</Button>
            ),
          },
        ]}
      />
      <Dialog
        open={selected !== null}
        onClose={() => setSelected(null)}
        fullWidth
        maxWidth="lg"
      >
        <DialogTitle>Customer data</DialogTitle>
        <DialogContent>
          {detail.isError && (
            <Alert severity="error">{detail.error.message}</Alert>
          )}
          {!customer ? (
            <Loading />
          ) : (
            <Stack spacing={3} sx={{ pt: 1 }}>
              <div>
                <Typography variant="h5">{customer.name}</Typography>
                <Typography color="text.secondary">
                  {customer.public_code} · {customer.mobile}
                  {customer.email && ` · ${customer.email}`}
                </Typography>
                <Chip
                  size="small"
                  sx={{ mt: 1 }}
                  label={
                    customer.source === "linked"
                      ? "Linked online and store customer"
                      : customer.source === "online"
                        ? "Online customer"
                        : "Store customer"
                  }
                />
              </div>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                {[
                  {
                    label: "Lifetime value",
                    value: money(customer.lifetime_value),
                  },
                  { label: "Store purchases", value: customer.pos_purchases },
                  { label: "Online orders", value: customer.online_orders },
                  {
                    label: "Returned value",
                    value: money(customer.returned_value),
                  },
                  { label: "Exchanges", value: customer.exchange_count },
                ].map((x) => (
                  <Paper
                    key={x.label}
                    variant="outlined"
                    sx={{ p: 2, flex: 1 }}
                  >
                    <Typography variant="caption" color="text.secondary">
                      {x.label}
                    </Typography>
                    <Typography variant="h6">{x.value}</Typography>
                  </Paper>
                ))}
              </Stack>
              <div>
                <Typography variant="h6" sx={{ mb: 1 }}>
                  Store sales history
                </Typography>
                <DataTable
                  rows={customer.sales}
                  columns={[
                    {
                      label: "Receipt",
                      value: (s) => <strong>{s.number}</strong>,
                    },
                    { label: "Branch", value: (s) => s.branch_name },
                    { label: "Date", value: (s) => date(s.created_at) },
                    {
                      label: "Payment",
                      value: (s) => s.payment_method.toUpperCase(),
                    },
                    { label: "Total", value: (s) => money(s.total) },
                    { label: "Returned", value: (s) => money(s.refunded) },
                    {
                      label: "Bill",
                      value: (s) => (
                        <Button onClick={() => setSaleBill(s)}>
                          View bill
                        </Button>
                      ),
                    },
                  ]}
                />
              </div>
              <div>
                <Typography variant="h6" sx={{ mb: 1 }}>
                  Online order history
                </Typography>
                <DataTable
                  rows={customer.orders}
                  columns={[
                    {
                      label: "Order",
                      value: (o) => <strong>{o.number}</strong>,
                    },
                    { label: "Branch", value: (o) => o.branch_name },
                    { label: "Date", value: (o) => date(o.created_at) },
                    { label: "Method", value: (o) => o.method },
                    {
                      label: "Status",
                      value: (o) => (
                        <Status value={o.display_status || o.status} />
                      ),
                    },
                    {
                      label: "Payment",
                      value: (o) => <Status value={o.payment_status} />,
                    },
                    { label: "Total", value: (o) => money(o.total) },
                  ]}
                />
              </div>
              <div>
                <Typography variant="h6" sx={{ mb: 1 }}>
                  Return & exchange history
                </Typography>
                <DataTable
                  rows={customer.returns_exchanges}
                  columns={[
                    {
                      label: "Receipt",
                      value: (x) => <strong>{x.number}</strong>,
                    },
                    { label: "Original", value: (x) => x.original_receipt },
                    { label: "Type", value: (x) => <Status value={x.kind} /> },
                    { label: "Date", value: (x) => date(x.created_at) },
                    {
                      label: "Return credit",
                      value: (x) => money(x.return_total),
                    },
                    {
                      label: "New items",
                      value: (x) => money(x.replacement_total),
                    },
                    {
                      label: "Bill",
                      value: (x) => (
                        <Button onClick={() => setExchangeBill(x)}>
                          View bill
                        </Button>
                      ),
                    },
                  ]}
                />
              </div>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelected(null)}>Close</Button>
        </DialogActions>
      </Dialog>
      <Receipt receipt={saleBill} close={() => setSaleBill(null)} />
      <ExchangeReceipt
        receipt={exchangeBill}
        close={() => setExchangeBill(null)}
      />
    </>
  );
}

function Settings() {
  const { notify } = useApp(),
    qc = useQueryClient();
  const [hours, setHours] = useState("1"),
    [busy, setBusy] = useState(false);
  const query = useQuery({
    queryKey: ["reservation-settings"],
    queryFn: () =>
      api<{ reservation_hours: number }>("/admin/settings/reservations"),
  });
  useEffect(() => {
    if (query.data) setHours(String(query.data.reservation_hours));
  }, [query.data]);
  async function save() {
    setBusy(true);
    try {
      await api("/admin/settings/reservations", {
        method: "PUT",
        body: JSON.stringify({ reservation_hours: Number(hours) }),
      });
      await qc.invalidateQueries({ queryKey: ["reservation-settings"] });
      notify(
        "Reservation duration updated. New online orders will use this duration.",
      );
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        title="Settings"
        subtitle="Configure backend-enforced business rules for the application."
      />
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}
      <Paper variant="outlined" sx={{ p: 3, maxWidth: 620 }}>
        <Typography variant="h6">Online order reservation</Typography>
        <Typography color="text.secondary" sx={{ mt: 1, mb: 3 }}>
          The branch must confirm a newly placed order within this period. After
          it expires, the backend releases its reserved stock.
        </Typography>
        <TextField
          fullWidth
          type="number"
          label="Reservation duration (hours)"
          value={hours}
          onChange={(e) => setHours(e.target.value)}
          inputProps={{ min: 1, max: 168, step: 1 }}
          error={
            Number(hours) < 1 ||
            Number(hours) > 168 ||
            !Number.isInteger(Number(hours))
          }
          helperText="Allowed range: 1–168 hours (up to 7 days). This applies to new orders only."
        />
        <Button
          variant="contained"
          sx={{ mt: 2 }}
          disabled={
            busy ||
            Number(hours) < 1 ||
            Number(hours) > 168 ||
            !Number.isInteger(Number(hours))
          }
          onClick={() => void save()}
        >
          {busy ? "Saving…" : "Save reservation duration"}
        </Button>
      </Paper>
    </>
  );
}

function AuditPage() {
  const query = useQuery({
    queryKey: ["audit"],
    queryFn: () =>
      api<
        {
          id: number;
          actor_id: number | null;
          action: string;
          reference: string;
          details: RecordData;
          created_at: string;
        }[]
      >("/admin/audit"),
  });
  return (
    <>
      <Heading
        title="Audit history"
        subtitle="A traceable record of significant changes. Most recent 200 events."
      />
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}
      <DataTable
        rows={query.data || []}
        columns={[
          { label: "Time", value: (a) => date(a.created_at) },
          { label: "Actor ID", value: (a) => a.actor_id || "System" },
          { label: "Action", value: (a) => <strong>{a.action}</strong> },
          { label: "Reference", value: (a) => a.reference },
          {
            label: "Details",
            value: (a) => (
              <Typography variant="caption">
                {Object.entries(a.details)
                  .map(([k, v]) => `${k}: ${String(v)}`)
                  .join(" · ") || "—"}
              </Typography>
            ),
          },
        ]}
      />
    </>
  );
}

type Shift = {
  id: number;
  actor_id: number;
  cashier: string;
  branch_id: number;
  branch_name: string;
  client_ip: string | null;
  system_info: string | null;
  opening_cash: string;
  counted_cash: string | null;
  expected_cash: string | null;
  current_expected: string;
  variance: string | null;
  counted_card: string | null;
  expected_card: string | null;
  current_expected_card: string;
  card_variance: string | null;
  counted_upi: string | null;
  expected_upi: string | null;
  current_expected_upi: string;
  upi_variance: string | null;
  opened_at: string;
  closed_at: string | null;
  closure_status: "open" | "pending" | "approved";
  closure_requested_at: string | null;
  shortage_reason: string | null;
  approved_at: string | null;
  approved_by: number | null;
};
function Shifts({ branch }: { branch: number }) {
  const { user, notify } = useApp(),
    qc = useQueryClient();
  const [open, setOpen] = useState(false),
    [closing, setClosing] = useState<Shift | null>(null),
    [cash, setCash] = useState("0"),
    [card, setCard] = useState("0"),
    [upi, setUpi] = useState("0"),
    [shortageReason, setShortageReason] = useState(""),
    [busy, setBusy] = useState(false);
  const query = useQuery({
    queryKey: ["shifts", branch],
    queryFn: () =>
      api<Shift[]>(branch ? `/shifts?branch_id=${branch}` : "/shifts"),
  });
  async function save() {
    setBusy(true);
    try {
      const r = await post<{
        variance?: string;
        card_variance?: string;
        upi_variance?: string;
      }>(
        closing ? `/shifts/${closing.id}/close` : "/shifts/open",
        closing
          ? {
              branch_id: branch,
              cash,
              card,
              upi,
              shortage_reason: shortageReason,
            }
          : { branch_id: branch, cash },
        key(),
      );
      setOpen(false);
      setClosing(null);
      setShortageReason("");
      await qc.invalidateQueries();
      notify(
        r.variance !== undefined
          ? `Closure submitted for manager approval · Cash ${money(r.variance)} · Card ${money(r.card_variance!)} · UPI ${money(r.upi_variance!)}`
          : "Shift opened. You can now complete POS sales.",
      );
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function approve(s: Shift) {
    setBusy(true);
    try {
      await post(`/shifts/${s.id}/approve-close`, {}, key());
      await qc.invalidateQueries();
      notify("Shift closure approved and finalised.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const reconcile = (
    expected: string,
    counted: string | null,
    variance: string | null,
  ) => (
    <Stack spacing={0.25}>
      <span>Expected: {money(expected)}</span>
      <span>Verified: {counted === null ? "—" : money(counted)}</span>
      {variance !== null && (
        <Typography
          variant="caption"
          color={Number(variance) === 0 ? "success.main" : "error.main"}
        >
          Variance: {money(variance)}
        </Typography>
      )}
    </Stack>
  );
  const canOpenShift = Boolean(user?.workspace_pages.includes("pos"));
  const shortage = Boolean(
    closing &&
      (Number(cash) < Number(closing.current_expected) ||
        Number(card) < Number(closing.current_expected_card) ||
        Number(upi) < Number(closing.current_expected_upi)),
  );
  return (
    <>
      <Heading
        title="Cashier shifts"
        subtitle="Cashiers submit reconciliations; a branch manager must approve every closure."
        action={
          canOpenShift ? (
            <Button
              variant="contained"
              disabled={query.data?.some(
                (s) => s.actor_id === user?.id && s.closure_status === "open",
              )}
              onClick={() => {
                setClosing(null);
                setCash("0");
                setCard("0");
                setUpi("0");
                setShortageReason("");
                setOpen(true);
              }}
            >
              Open my shift
            </Button>
          ) : undefined
        }
      />
      <Alert severity="info" sx={{ mb: 3 }}>
        Enter verified cash, card, and UPI totals. A shortage requires an
        explanation, and every submitted closure remains pending until the
        branch manager approves it.
      </Alert>
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}
      <DataTable
        rows={query.data || []}
        columns={[
          {
            label: "Cashier",
            value: (s) => (
              <>
                {s.cashier}
                {branch === 0 && (
                  <Typography variant="caption" display="block">
                    {s.branch_name}
                  </Typography>
                )}
              </>
            ),
          },
          { label: "Opened", value: (s) => date(s.opened_at) },
          {
            label: "Cash",
            value: (s) =>
              reconcile(
                s.expected_cash ?? s.current_expected,
                s.counted_cash,
                s.variance,
              ),
          },
          {
            label: "Card",
            value: (s) =>
              reconcile(
                s.expected_card ?? s.current_expected_card,
                s.counted_card,
                s.card_variance,
              ),
          },
          {
            label: "UPI",
            value: (s) =>
              reconcile(
                s.expected_upi ?? s.current_expected_upi,
                s.counted_upi,
                s.upi_variance,
              ),
          },
          { label: "Reason", value: (s) => s.shortage_reason || "—" },
          {
            label: "Status",
            value: (s) => (
              <Status
                value={
                  s.closure_status === "pending"
                    ? "approval_pending"
                    : s.closure_status
                }
              />
            ),
          },
          {
            label: "Action",
            value: (s) =>
              s.closure_status === "open" && s.actor_id === user?.id ? (
                <Button
                  onClick={() => {
                    setClosing(s);
                    setCash(s.current_expected);
                    setCard(s.current_expected_card);
                    setUpi(s.current_expected_upi);
                    setShortageReason("");
                    setOpen(true);
                  }}
                >
                  Close shift
                </Button>
              ) : s.closure_status === "pending" && user?.role === "manager" ? (
                <Button
                  variant="contained"
                  disabled={busy}
                  onClick={() => void approve(s)}
                >
                  Approve closure
                </Button>
              ) : null,
          },
        ]}
      />
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>
          {closing ? "Submit shift closure" : "Open cashier shift"}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {closing ? (
              <>
                <Alert severity="info">
                  Verify every payment total. Submission stops further billing
                  and requires branch-manager approval.
                </Alert>
                <TextField
                  type="number"
                  label={`Physical cash · expected ${money(closing.current_expected)}`}
                  value={cash}
                  onChange={(e) => setCash(e.target.value)}
                  inputProps={{ min: 0, step: 0.01 }}
                />
                <TextField
                  type="number"
                  label={`Card total · expected ${money(closing.current_expected_card)}`}
                  value={card}
                  onChange={(e) => setCard(e.target.value)}
                  inputProps={{ min: 0, step: 0.01 }}
                />
                <TextField
                  type="number"
                  label={`UPI total · expected ${money(closing.current_expected_upi)}`}
                  value={upi}
                  onChange={(e) => setUpi(e.target.value)}
                  inputProps={{ min: 0, step: 0.01 }}
                />
                {shortage && (
                  <TextField
                    required
                    label="Shortage reason"
                    value={shortageReason}
                    onChange={(e) => setShortageReason(e.target.value)}
                    multiline
                    minRows={2}
                    helperText="Required because at least one counted total is below the expected amount."
                  />
                )}
              </>
            ) : (
              <TextField
                type="number"
                label="Opening cash float"
                value={cash}
                onChange={(e) => setCash(e.target.value)}
                inputProps={{ min: 0, step: 0.01 }}
              />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={
              busy ||
              Number(cash) < 0 ||
              Number(card) < 0 ||
              Number(upi) < 0 ||
              (shortage && shortageReason.trim().length < 3)
            }
            onClick={() => void save()}
          >
            {closing ? "Submit for approval" : "Open shift"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

type Count = {
  id: number;
  variant_id: number;
  actor_id: number;
  branch_name: string;
  name: string;
  sku: string;
  system_quantity: string;
  counted_quantity: string;
  reason: string;
  status: string;
};
function StockCounts({ branch }: { branch: number }) {
  const { user, catalogue, notify } = useApp(),
    qc = useQueryClient();
  const [open, setOpen] = useState(false),
    [variant, setVariant] = useState(""),
    [counted, setCounted] = useState("0"),
    [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false);
  const query = useQuery({
    queryKey: ["counts", branch],
    queryFn: () =>
      api<Count[]>(
        branch ? `/stock-counts?branch_id=${branch}` : "/stock-counts",
      ),
  });
  async function submit() {
    if (!branch) {
      notify("Select a specific branch before submitting a stock count.");
      return;
    }
    setBusy(true);
    try {
      await post(
        "/stock-counts",
        {
          branch_id: branch,
          variant_id: Number(variant),
          counted_quantity: counted,
          reason,
        },
        key(),
      );
      setOpen(false);
      setReason("");
      await qc.invalidateQueries();
      notify("Count submitted for another manager to approve.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function action(c: Count, type: string) {
    try {
      await post(`/stock-counts/${c.id}/${type}`, {}, key());
      await qc.invalidateQueries();
      notify("Count " + type + "d.");
    } catch (err) {
      notify((err as Error).message);
    }
  }
  return (
    <>
      <Heading
        title="Stock counts & approval"
        subtitle="Count physical on-hand stock, including damaged goods. A different manager approves the variance."
        action={
          <Button variant="contained" onClick={() => setOpen(true)}>
            Submit count
          </Button>
        }
      />
      <Alert severity="info" sx={{ mb: 3 }}>
        Count during a controlled window. If stock moves before approval, reject
        the stale count and count again.
      </Alert>
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}
      <DataTable
        rows={query.data || []}
        columns={[
          { label: "Count", value: (c) => `COUNT-${c.id}` },
          { label: "SKU / option", value: (c) => `${c.sku} · ${c.name}` },
          {
            label: "System on-hand",
            value: (c) => quantity(c.system_quantity),
          },
          { label: "Counted", value: (c) => quantity(c.counted_quantity) },
          {
            label: "Variance",
            value: (c) =>
              quantity(Number(c.counted_quantity) - Number(c.system_quantity)),
          },
          { label: "Reason", value: (c) => c.reason },
          { label: "Status", value: (c) => <Status value={c.status} /> },
          {
            label: "Action",
            value: (c) =>
              c.status === "pending" &&
              ["admin", "manager"].includes(user!.role) ? (
                <>
                  <Button
                    disabled={c.actor_id === user?.id}
                    onClick={() => void action(c, "approve")}
                  >
                    Approve
                  </Button>
                  <Button
                    color="error"
                    onClick={() => void action(c, "reject")}
                  >
                    Reject
                  </Button>
                </>
              ) : null,
          },
        ]}
      />
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Submit physical stock count</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              select
              label="Product variant"
              value={variant}
              onChange={(e) => setVariant(e.target.value)}
            >
              {catalogue.flatMap((p) =>
                p.variants.map((v) => (
                  <MenuItem key={v.id} value={v.id}>
                    {p.name} · {v.label}
                  </MenuItem>
                )),
              )}
            </TextField>
            <TextField
              type="number"
              label="Counted on-hand quantity"
              value={counted}
              onChange={(e) => setCounted(e.target.value)}
              inputProps={{ min: 0, step: 0.001 }}
            />
            <TextField
              label="Count reason / notes"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={
              busy || !variant || Number(counted) < 0 || reason.length < 3
            }
            onClick={() => void submit()}
          >
            Submit for approval
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
