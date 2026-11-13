import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Divider,
  FormControlLabel,
  MenuItem,
  Paper,
  Radio,
  RadioGroup,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import SearchOutlined from "@mui/icons-material/SearchOutlined";
import Add from "@mui/icons-material/Add";
import Remove from "@mui/icons-material/Remove";
import NearMeOutlined from "@mui/icons-material/NearMeOutlined";
import LocalShippingOutlined from "@mui/icons-material/LocalShippingOutlined";
import StorefrontOutlined from "@mui/icons-material/StorefrontOutlined";
import SpaOutlined from "@mui/icons-material/SpaOutlined";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, key, money, post, quantity, date, amount } from "./api";
import { useApp } from "./context";
import { useConfirmDialog } from "./ConfirmDialog";
import type { Branch, BranchOption, Order, Product } from "./types";
import { OrderPaymentSummary } from "./OrderPayment";
import SavedAddresses from "./SavedAddresses";

function ProductArt({ product }: { product: Product }) {
  return (
    <div className={"product-art " + product.tone}>
      <span className="art-circle" />
      <div className={"pack " + (product.category === "Oil" ? "bottle" : "")}>
        <div className="pack-fold" />
        <div className="pack-label">
          <SpaOutlined fontSize="small" />
          <strong>CHINNU</strong>
          <span>{product.category.toUpperCase()}</span>
          <i>{product.name.split(" ").slice(-2).join(" ")}</i>
        </div>
      </div>
      <span className="art-seeds">• • •</span>
    </div>
  );
}
function ProductCard({ product }: { product: Product }) {
  const [selected, setSelected] = useState(product.variants[0]?.id),
    [qty, setQty] = useState(Number(product.variants[0]?.min_qty || 1));
  const { add } = useApp();
  const v =
    product.variants.find((x) => x.id === selected) || product.variants[0];
  if (!v) return null;
  const inStock = Number(v.available_somewhere) >= Number(v.min_qty);
  return (
    <Paper className="product-card" variant="outlined">
      <ProductArt product={product} />
      <div className="product-info">
        <span className="eyebrow small">{product.category}</span>
        <Typography
          variant="h6"
          sx={{ fontSize: 17, minHeight: 48, lineHeight: 1.4 }}
        >
          {product.name}
        </Typography>
        <Typography
          variant="body2"
          color="text.secondary"
          className="product-description"
        >
          {product.description}
        </Typography>
        <TextField
          select
          fullWidth
          label="Choose size"
          size="small"
          value={v.id}
          onChange={(e) => {
            const opt = product.variants.find(
              (x) => x.id === Number(e.target.value),
            )!;
            setSelected(opt.id);
            setQty(Number(opt.min_qty));
          }}
          sx={{ mt: 2 }}
        >
          {product.variants.map((x) => (
            <MenuItem key={x.id} value={x.id}>
              {x.label}
            </MenuItem>
          ))}
        </TextField>
        <div className="price-row">
          <strong>{money(v.price)}</strong>
          <span>/{v.unit === "pack" ? "pack" : v.unit}</span>
        </div>
        <Stack direction="row" spacing={1} alignItems="center">
          <TextField
            type="number"
            label="Quantity"
            value={qty}
            onChange={(e) => setQty(Number(e.target.value))}
            inputProps={{
              min: Number(v.min_qty),
              max: Number(v.max_qty),
              step: Number(v.step),
            }}
            sx={{ width: 100 }}
          />
          <Button
            fullWidth
            variant="contained"
            startIcon={<Add />}
            disabled={
              !inStock ||
              qty < Number(v.min_qty) ||
              qty > Number(v.max_qty) ||
              Math.abs(
                (qty - Number(v.min_qty)) / Number(v.step) -
                  Math.round((qty - Number(v.min_qty)) / Number(v.step)),
              ) > 0.00001
            }
            onClick={() => add(v.id, qty)}
          >
            Add
          </Button>
        </Stack>
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: "block", mt: 1 }}
        >
          {inStock
            ? "Branch availability checked at checkout"
            : "Currently unavailable"}
        </Typography>
      </div>
    </Paper>
  );
}

export function Shop({ loading }: { loading: boolean }) {
  const { catalogue } = useApp();
  const [search, setSearch] = useState(""),
    [category, setCategory] = useState("All");
  const location = useLocation();
  const branches = useQuery({
    queryKey: ["public-branches"],
    queryFn: () => api<Branch[]>("/branches"),
  });
  useEffect(() => {
    if (location.hash) {
      requestAnimationFrame(() =>
        document
          .getElementById(location.hash.slice(1))
          ?.scrollIntoView({ behavior: "smooth", block: "start" }),
      );
    }
  }, [location.hash, branches.isPending]);
  const categories = ["All", ...new Set(catalogue.map((x) => x.category))];
  const filtered = catalogue.filter(
    (x) =>
      (category === "All" || x.category === category) &&
      (
        x.code +
        " " +
        x.name +
        " " +
        x.description +
        " " +
        x.variants.map((v) => v.sku).join(" ")
      )
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <>
      <Container className="storefront" maxWidth="xl" sx={{ pt: 3, pb: 7 }}>
        <section className="hero">
          <div className="hero-copy">
            <span className="eyebrow">
              PURE GRAINS · HEALTHY CATTLE · BETTER TOMORROW
            </span>
            <h1>
              Quality grains.
              <br />
              <em>From CHINNU.</em>
            </h1>
            <p>
              Rice, oils, nuts, cattle feed, and everyday essentials.
              <br />
              Shop online. Collect nearby. Or get it delivered.
            </p>
            <Button variant="contained" size="large" href="#shop">
              Explore products <span className="button-arrow">↗</span>
            </Button>
            <Button variant="text" size="large" href="#branches" sx={{ml:1}}>Find a branch</Button>
            <div className="hero-foot">
              <span>
                <StorefrontOutlined />
                Your local branches
              </span>
              <span>
                <LocalShippingOutlined />
                Delivery & pickup
              </span>
            </div>
          </div>
          <div className="hero-visual">
            <img src="/chinnu-logo-transparent.png" alt="CHINNU" className="hero-logo" />
          </div>
        </section>
        <div className="benefit-strip">
          <span>One price. Every branch.</span>
          <span>Flexible packs & loose quantities</span>
          <span>Choose your branch at checkout</span>
        </div>
        <section id="shop">
          <div className="section-top">
            <div>
              <span className="eyebrow">THE CHINNU COLLECTION</span>
              <h2>Everyday essentials, thoughtfully chosen.</h2>
            </div>
            <TextField
              label="Search products"
              placeholder="Try rice, nuts, or a SKU"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              slotProps={{
                input: {
                  startAdornment: (
                    <SearchOutlined sx={{ mr: 1, color: "text.secondary" }} />
                  ),
                },
              }}
            />
          </div>
          <Stack
            direction="row"
            spacing={1}
            sx={{ mb: 3, overflowX: "auto", pb: 1 }}
          >
            {categories.map((c) => (
              <Chip
                key={c}
                label={c}
                color={c === category ? "primary" : "default"}
                variant={c === category ? "filled" : "outlined"}
                onClick={() => setCategory(c)}
                sx={{ px: 1 }}
              />
            ))}
          </Stack>
          <div className="product-grid">
            {loading
              ? [1, 2, 3, 4].map((x) => (
                  <Skeleton key={x} variant="rounded" height={450} />
                ))
              : filtered.map((p) => <ProductCard key={p.id} product={p} />)}
          </div>
          {!loading && !filtered.length && (
            <Alert severity="info">No products match your search.</Alert>
          )}
        </section>
        <section id="branches" className="locations-section">
          <div className="section-top">
            <div>
              <span className="eyebrow">FIND CHINNU NEAR YOU</span>
              <h2>Our branches</h2>
              <Typography color="text.secondary">
                View every active branch and open its exact coordinates in
                Google Maps.
              </Typography>
            </div>
          </div>
          {branches.isError && (
            <Alert severity="error">
              Branch locations could not be loaded.
            </Alert>
          )}
          <div className="locations-grid">
            {branches.isPending
              ? [1, 2, 3, 4].map((x) => (
                  <Skeleton key={x} variant="rounded" height={230} />
                ))
              : branches.data?.map((branch) => (
                  <Paper
                    key={branch.id}
                    variant="outlined"
                    className="location-card"
                  >
                    <StorefrontOutlined className="location-icon" />
                    <div>
                      <Typography variant="h6">{branch.name}</Typography>
                      <Typography color="text.secondary" sx={{ mt: 1 }}>
                        {branch.address}
                      </Typography>
                    </div>
                    <Stack spacing={1}>
                      <Typography variant="body2">
                        <strong>Hours:</strong> {branch.hours}
                      </Typography>
                      <Typography variant="body2">
                        <strong>Delivery coverage:</strong> {branch.radius_km}{" "}
                        km
                      </Typography>
                      <Chip
                        size="small"
                        label={
                          branch.accepting_orders
                            ? "Accepting online orders"
                            : "Online orders paused"
                        }
                        color={branch.accepting_orders ? "success" : "default"}
                        sx={{ alignSelf: "flex-start" }}
                      />
                    </Stack>
                    <Button
                      variant="outlined"
                      startIcon={<NearMeOutlined />}
                      href={`https://www.google.com/maps/search/?api=1&query=${branch.latitude},${branch.longitude}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      View in Google Maps
                    </Button>
                  </Paper>
                ))}
          </div>
        </section>
      </Container>
      <footer className="store-footer">
        <Container maxWidth="xl" sx={{ flexDirection: "column", justifyContent: "center", textAlign: "center" }}>
          <strong>CHINNU</strong>
          <span>Copyright © {new Date().getFullYear()} Chinnu Modern Rice Mills. All rights reserved.</span>
        </Container>
      </footer>
    </>
  );
}

export function Checkout() {
  const { cart, setCart, catalogue, user, notify } = useApp(),
    navigate = useNavigate(),
    qc = useQueryClient();
  const [draft] = useState(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem("chinnu-checkout-draft") || "null");
      if (saved && Date.now() - saved.savedAt < 3600000 && saved.cart === JSON.stringify(cart)
          && ["delivery", "pickup"].includes(saved.method)
          && [saved.address, saved.phone, saved.lat, saved.lon].every(x => typeof x === "string")) return saved;
    } catch { /* Storage unavailable or an invalid draft: start normally. */ }
    return null;
  });
  const [method, setMethod] = useState<string>(draft?.method || "delivery"),
    [address, setAddress] = useState<string>(draft?.address || ""),
    [phone, setPhone] = useState<string>(draft?.phone || ""),
    [lat, setLat] = useState<string>(draft?.lat || ""),
    [lon, setLon] = useState<string>(draft?.lon || "");
  const [options, setOptions] = useState<BranchOption[] | null>(null),
    [selected, setSelected] = useState(0),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const defaults = useQuery({
    queryKey: ["checkout-defaults", user?.id],
    queryFn: () =>
      api<{ phone: string; address: string }>("/checkout/defaults"),
    enabled: !!user,
  });
  const requestKey = useRef("");
  const enriched = cart.map((line) => {
    const product = catalogue.find((p) =>
      p.variants.some((v) => v.id === line.variant_id),
    );
    return {
      ...line,
      product,
      variant: product?.variants.find((v) => v.id === line.variant_id),
    };
  });
  const subtotal = enriched.reduce(
      (s, x) => s + amount(x.variant?.price || 0, x.quantity),
      0,
    ),
    branch = options?.find((b) => b.id === selected),
    displayDelivery =
      method === "pickup" || branch?.requires_approval
        ? 0
        : Number(branch?.delivery_fee || 0);
  useEffect(() => {
    setOptions(null);
    setSelected(0);
    requestKey.current = "";
    if (draft && method === draft.method && lat === draft.lat && lon === draft.lon
        && JSON.stringify(cart) === draft.cart) {
      let active = true;
      // Never trust cached branch eligibility, prices or stock after sign-in.
      post<BranchOption[]>("/checkout/branches", {items: cart, method, latitude: Number(lat), longitude: Number(lon)})
        .then(result => {
          if (!active) return;
          setOptions(result);
          setSelected(result.some(b => b.id === draft.selected && b.eligible) ? draft.selected : 0);
        }).catch(err => { if (active) setError((err as Error).message); });
      return () => { active = false; };
    }
  }, [JSON.stringify(cart), method, lat, lon]);
  useEffect(() => {
    requestKey.current = "";
  }, [address, phone]);
  useEffect(() => {
    if (defaults.data) {
      setPhone((current) => current || defaults.data.phone);
      setAddress((current) => current || defaults.data.address);
    }
  }, [defaults.data]);
  async function locate() {
    setError("");
    if (!navigator.geolocation) {
      setError("Location is unavailable. Enter coordinates below.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setLat(p.coords.latitude.toFixed(7));
        setLon(p.coords.longitude.toFixed(7));
      },
      () =>
        setError(
          "Location permission was not granted. Enter coordinates or use the demo location.",
        ),
    );
  }
  function payload() {
    return {
      items: cart,
      method,
      latitude: Number(lat),
      longitude: Number(lon),
    };
  }
  async function find() {
    setBusy(true);
    setError("");
    try {
      if (!lat || !lon) throw new Error("Set your location first.");
      const result = await post<BranchOption[]>(
        "/checkout/branches",
        payload(),
      );
      setOptions(result);
      setSelected(result.find((x) => x.recommended)?.id || 0);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function order() {
    if (!user) {
      try {
        sessionStorage.setItem("chinnu-checkout-draft", JSON.stringify({method,address,phone,lat,lon,selected,cart:JSON.stringify(cart),savedAt:Date.now()}));
      } catch {
        setError("Unable to save checkout details. Please enable browser storage before signing in.");
        return;
      }
      navigate("/login", {state: {returnTo: "/checkout"}});
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (!requestKey.current) requestKey.current = key();
      const placed = await post<{ id: number; requires_approval: boolean }>(
        "/orders",
        {
          ...payload(),
          branch_id: selected,
          address,
          phone,
          expected_subtotal: subtotal.toFixed(2),
        },
        requestKey.current,
      );
      setCart([]);
      sessionStorage.removeItem("chinnu-checkout-draft");
      await qc.invalidateQueries();
      notify(
        placed.requires_approval
          ? "Order placed. The branch manager will review delivery within 24 hours."
          : "Order placed. Your branch will confirm it shortly.",
      );
      navigate("/orders");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!cart.length)
    return (
      <Container sx={{ py: 8, textAlign: "center" }}>
        <ShoppingEmpty />
        <Typography variant="h4" gutterBottom>
          Your basket is waiting.
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          Add a few pantry favourites to get started.
        </Typography>
        <Button component={Link} to="/" variant="contained">
          Explore the shop
        </Button>
      </Container>
    );
  return (
    <Container className="customer-checkout" maxWidth="lg" sx={{ py: 5 }}>
      <span className="eyebrow">YOUR NEXT GROCERY RUN</span>
      <Typography variant="h4" sx={{ mb: 1 }}>
        Your basket & checkout
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 4 }}>
        Choose how you receive your groceries, then select a branch.
      </Typography>
      <div className="checkout-grid">
        <Stack spacing={3}>
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              1. Review your basket
            </Typography>
            {enriched.map((x) => (
              <div className="cart-row" key={x.variant_id}>
                <div>
                  <strong>{x.product?.name || "Unavailable product"}</strong>
                  <Typography variant="body2" color="text.secondary">
                    {x.variant?.label} · {money(x.variant?.price || 0)}/
                    {x.variant?.unit}
                  </Typography>
                </div>
                <TextField
                  type="number"
                  label="Qty"
                  value={x.quantity}
                  inputProps={{
                    min: Number(x.variant?.min_qty || 1),
                    step: Number(x.variant?.step || 1),
                    max: Number(x.variant?.max_qty || 100),
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
                  sx={{ width: 95 }}
                />
                <strong>
                  {money(amount(x.variant?.price || 0, x.quantity))}
                </strong>
                <Button
                  size="small"
                  color="inherit"
                  onClick={() =>
                    setCart(cart.filter((c) => c.variant_id !== x.variant_id))
                  }
                >
                  Remove
                </Button>
              </div>
            ))}
          </Paper>
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              2. Delivery or pickup
            </Typography>
            <RadioGroup
              row
              value={method}
              onChange={(e) => setMethod(e.target.value)}
            >
              <FormControlLabel
                value="delivery"
                control={<Radio />}
                label="Home delivery"
              />
              <FormControlLabel
                value="pickup"
                control={<Radio />}
                label="Shop pickup"
              />
            </RadioGroup>
            <Stack spacing={2} sx={{ mt: 2 }}>
              {method === "delivery" && user?.role === "customer" && <SavedAddresses
                key={user.id} userId={user.id} address={address} phone={phone} lat={lat} lon={lon}
                onSelect={(savedAddress, savedPhone, latitude, longitude) => {
                  setAddress(savedAddress); setPhone(savedPhone); setLat(latitude); setLon(longitude);
                  setOptions(null); setSelected(0);
                }}
              />}
              {method === "delivery" && (
                <TextField
                  label="Complete delivery address"
                  multiline
                  minRows={2}
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                />
              )}
              <TextField
                label="Contact mobile"
                value={phone}
                onChange={(e) =>
                  setPhone(e.target.value.replace(/\D/g, "").slice(0, 10))
                }
                inputProps={{
                  inputMode: "numeric",
                  pattern: "[6-9][0-9]{9}",
                  maxLength: 10,
                }}
                helperText={
                  user?.phone
                    ? "Fetched from your account. You can use another contact number for this order."
                    : "Enter a 10-digit contact number."
                }
              />
              <Typography variant="body2" color="text.secondary">
                Set a location to recommend your nearest branch. Distances are straight-line estimates.
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                <Button
                  variant="outlined"
                  startIcon={<NearMeOutlined />}
                  onClick={() => void locate()}
                >
                  Use my location
                </Button>
                <Button
                  onClick={() => {
                    setLat("11.3410");
                    setLon("77.7172");
                  }}
                >
                  Use demo location
                </Button>
              </Stack>
              <Stack direction="row" spacing={2}>
                <TextField
                  label="Latitude"
                  type="number"
                  value={lat}
                  onChange={(e) => setLat(e.target.value)}
                  inputProps={{ min: -90, max: 90, step: "any" }}
                />
                <TextField
                  label="Longitude"
                  type="number"
                  value={lon}
                  onChange={(e) => setLon(e.target.value)}
                  inputProps={{ min: -180, max: 180, step: "any" }}
                />
              </Stack>
              <Typography variant="caption" color="text.secondary">
                Demo branches are in Erode. Address geocoding is not connected;
                coordinates or browser location are required.
              </Typography>
              <Button
                variant="contained"
                disabled={busy}
                onClick={() => void find()}
              >
                Find available branches
              </Button>
            </Stack>
          </Paper>
          {options && (
            <Paper variant="outlined" sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                3. Choose your branch
              </Typography>
              {!options.some((b) => b.eligible) && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  No branch currently has every item in this basket.
                </Alert>
              )}
              <RadioGroup
                value={selected}
                onChange={(e) => {
                  setSelected(Number(e.target.value));
                  requestKey.current = "";
                }}
              >
                {options.map((b) => (
                  <div
                    className={
                      "branch-option " + (selected === b.id ? "selected" : "")
                    }
                    key={b.id}
                  >
                    <FormControlLabel
                      disabled={!b.eligible}
                      value={b.id}
                      control={<Radio />}
                      label={
                        <Box>
                          <Stack direction="row" gap={1} alignItems="center">
                            <strong>{b.name}</strong>
                            {b.recommended && (
                              <Chip
                                size="small"
                                color="primary"
                                label="Recommended"
                              />
                            )}
                            {b.requires_approval && b.eligible && (
                              <Chip
                                size="small"
                                color="warning"
                                label="Manager approval"
                              />
                            )}
                          </Stack>
                          <Typography variant="body2" color="text.secondary">
                            {b.distance_km} km · {b.address}
                          </Typography>
                          <Typography variant="caption">
                            {b.hours} ·{" "}
                            {method === "delivery"
                              ? `Delivery ${money(b.delivery_fee)}`
                              : "Pay at pickup"}
                          </Typography>
                        </Box>
                      }
                    />
                    {b.missing.length > 0 && (
                      <Typography color="error" variant="body2">
                        Unavailable: {b.missing.join(", ")}
                      </Typography>
                    )}
                    {b.requires_approval && b.eligible && (
                      <Alert severity="warning" sx={{ mt: 1 }}>
                        Outside the normal delivery radius. You may place the
                        order; the branch manager will approve or reject
                        delivery within 24 hours.
                      </Alert>
                    )}
                  </div>
                ))}
              </RadioGroup>
            </Paper>
          )}
        </Stack>
        <Paper variant="outlined" className="checkout-summary" sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Order summary
          </Typography>
          <div className="total-line">
            <span>Products</span>
            <strong>{money(subtotal)}</strong>
          </div>
          <div className="total-line">
            <span>Delivery</span>
            <strong>
              {method === "pickup"
                ? "Free"
                : branch?.requires_approval
                  ? "Set by manager"
                  : branch
                    ? money(branch.delivery_fee)
                    : "Select branch"}
            </strong>
          </div>
          <Divider sx={{ my: 2 }} />
          <div className="total-line grand">
            <span>
              {branch?.requires_approval ? "Current subtotal" : "Total"}
            </span>
            <strong>{money(subtotal + displayDelivery)}</strong>
          </div>
          <Alert severity="info" sx={{ my: 3 }}>
            {method === "delivery" ? "Cash on delivery" : "Pay at the shop"}.
            Online payment will be added later.
          </Alert>
          {branch?.requires_approval && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              This address is outside normal coverage. The manager will set the
              delivery charge and estimated delivery days during review. Your
              final total will then be updated.
            </Alert>
          )}
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          {!user && (
            <Typography variant="body2" sx={{ mb: 2 }}>
              Sign in before placing your order. Your basket will stay here.
            </Typography>
          )}
          <Button
            fullWidth
            variant="contained"
            size="large"
            disabled={
              busy ||
              !branch?.eligible ||
              !/^[6-9][0-9]{9}$/.test(phone) ||
              (method === "delivery" && address.trim().length < 8)
            }
            onClick={() => void order()}
          >
            {busy
              ? "Please wait…"
              : user
                ? "Place order"
                : "Sign in to continue"}
          </Button>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: "block", mt: 2 }}
          >
            {branch?.requires_approval
              ? "Stock is reserved while the manager reviews delivery for up to 24 hours."
              : "Stock is checked again when you place the order. The branch must confirm within its configured reservation period."}
          </Typography>
        </Paper>
      </div>
    </Container>
  );
}
function ShoppingEmpty() {
  return <SpaOutlined sx={{ fontSize: 70, color: "primary.main", mb: 2 }} />;
}

export function CustomerOrders() {
  const { user, notify } = useApp(),
    qc = useQueryClient();
  const confirmation = useConfirmDialog();
  const query = useQuery({
    queryKey: ["orders", user?.id],
    queryFn: () => api<Order[]>("/orders"),
    refetchInterval: 15000,
  });
  async function cancel(o: Order) {
    if (
      !(await confirmation.ask(
        "Cancel this order and release its reserved stock?",
        { title: "Cancel order", confirmLabel: "Cancel order", danger: true },
      ))
    )
      return;
    try {
      await post(
        `/orders/${o.id}/transition`,
        { action: "cancel", note: "Customer cancellation" },
        key(),
      );
      await qc.invalidateQueries();
      notify("Order cancelled");
    } catch (err) {
      notify((err as Error).message);
    }
  }
  return (
    <Container maxWidth="md" sx={{ py: 5 }}>
      <span className="eyebrow">FROM OUR SHELVES TO YOUR HOME</span>
      <Typography variant="h4" sx={{ mb: 3 }}>
        Your orders
      </Typography>
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}
      {query.isPending && <Skeleton height={200} />}
      <Stack spacing={3}>
        {query.data?.map((o) => (
          <Paper variant="outlined" key={o.id} sx={{ p: 3 }}>
            <Stack
              direction="row"
              justifyContent="space-between"
              flexWrap="wrap"
              gap={1}
            >
              <div>
                <Typography variant="h6">{o.number}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {date(o.created_at)} · {o.branch_name}
                </Typography>
              </div>
              <Stack direction="row" gap={1}>
                <Chip
                  label={o.status.replaceAll("_", " ")}
                  color={
                    o.status === "completed"
                      ? "success"
                      : o.status === "cancelled"
                        ? "default"
                        : "primary"
                  }
                />
                <Chip label={o.payment_status} variant="outlined" />
              </Stack>
            </Stack>
            {o.method === "delivery" &&
              ["ready", "dispatched"].includes(o.status) && (
                <Alert
                  severity={o.pickup_code ? "info" : "warning"}
                  sx={{ mt: 2 }}
                  action={!o.pickup_code ? (
                    <Button color="inherit" onClick={() => void query.refetch()}>
                      Refresh
                    </Button>
                  ) : undefined}
                >
                  <Typography variant="subtitle2">Delivery OTP</Typography>
                  {o.pickup_code ? (
                    <>
                      <Typography
                        component="div"
                        aria-label="Delivery OTP"
                        sx={{ fontSize: { xs: 28, sm: 34 }, fontWeight: 700, letterSpacing: ".2em", my: .5 }}
                      >
                        {o.pickup_code}
                      </Typography>
                      Share this code with the delivery person only after receiving your order.
                    </>
                  ) : (
                    "Your delivery OTP could not be loaded. Refresh your orders or contact the branch."
                  )}
                </Alert>
              )}
            {o.status === "approval_pending" && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                Your order has been placed and is awaiting delivery approval
                from the branch manager. It will be reviewed within 24 hours.
                The manager will set the delivery charge and estimated delivery
                days.
              </Alert>
            )}
            {o.coverage_approval_required && o.coverage_approved_at && (
              <Alert severity="success" sx={{ mt: 2 }}>
                Delivery approved · Delivery charge:{" "}
                <strong>{money(o.delivery_fee)}</strong> · Estimated delivery:{" "}
                <strong>{o.estimated_delivery_days} day(s)</strong>.
              </Alert>
            )}
            <Divider sx={{ my: 2 }} />
            {o.items.map((x) => (
              <div className="total-line" key={x.id}>
                <span>
                  {x.name} × {quantity(x.quantity)} {x.unit}
                </span>
                <span>{money(x.line_total)}</span>
              </div>
            ))}
            <div className="total-line">
              <span>Delivery charge</span>
              <strong>
                {o.status === "approval_pending"
                  ? "Pending approval"
                  : money(o.delivery_fee)}
              </strong>
            </div>
            <div className="total-line">
              <strong>
                {o.status === "approval_pending"
                  ? "Current subtotal"
                  : "Total including delivery"}
              </strong>
              <strong>{money(o.total)}</strong>
            </div>
            {o.payment_collection && <Box sx={{ mt: 2 }}><OrderPaymentSummary collection={o.payment_collection} /></Box>}
            <Typography variant="body2" sx={{ mt: 2 }}>
              {o.method === "delivery"
                ? `Deliver to: ${o.address}`
                : `Pickup at: ${o.branch_address}`}
            </Typography>
            {o.method === "pickup" && o.status !== "cancelled" && (
              <Alert severity="info" sx={{ mt: 2 }}>
                Your pickup code: <strong>{o.pickup_code}</strong>. Share it at
                collection.
              </Alert>
            )}
            <div className="order-timeline">
              {o.events.map((e) => (
                <div key={e.id} data-tone={e.tone || "neutral"}>
                  <span className="timeline-dot" />
                  <strong>{(e.display_status || e.status).replaceAll("_", " ")}</strong>
                  <span>{date(e.created_at)}</span>
                  {e.note && <small>{e.note}</small>}
                </div>
              ))}
            </div>
            {["placed", "approval_pending"].includes(o.status) && (
              <Button color="error" onClick={() => void cancel(o)}>
                Cancel order
              </Button>
            )}
          </Paper>
        ))}
      </Stack>
      {query.data?.length === 0 && (
        <Paper variant="outlined" sx={{ p: 5, textAlign: "center" }}>
          <Typography sx={{ mb: 2 }}>Your orders will appear here.</Typography>
          <Button component={Link} to="/" variant="contained">
            Start shopping
          </Button>
        </Paper>
      )}
    </Container>
  );
}

type Tracking={number:string;status:string;display_status:string;branch_name:string;driver_name:string|null;destination_latitude:string|null;destination_longitude:string|null;driver_latitude:string|null;driver_longitude:string|null;location_updated_at:string|null;events:{id:number;status:string;note:string;created_at:string}[]};
export function CustomerOrderTracking(){
  const {id}=useParams();
  const query=useQuery({queryKey:['order-tracking',id],queryFn:()=>api<Tracking>(`/orders/${id}/tracking`),refetchInterval:10000});
  const tracking=query.data;
  const mapUrl=tracking?.driver_latitude&&tracking.driver_longitude?`https://www.google.com/maps/search/?api=1&query=${tracking.driver_latitude},${tracking.driver_longitude}`:'';
  return <Container maxWidth="md" sx={{py:5}}><Button component={Link} to="/orders">← My orders</Button><Typography variant="h4" sx={{my:2}}>Delivery tracking</Typography>
    {query.isPending&&<Skeleton height={300}/>} {query.isError&&<Alert severity="error">{query.error.message}</Alert>}
    {tracking&&<Stack spacing={2}><Paper variant="outlined" sx={{p:3}}><Stack direction="row" justifyContent="space-between" gap={2}><div><Typography variant="h5">{tracking.number}</Typography><Typography color="text.secondary">{tracking.branch_name}</Typography></div><Chip color="primary" label={tracking.display_status.replaceAll('_',' ')}/></Stack></Paper>
      <Paper variant="outlined" sx={{p:3}}><Typography variant="h6">Delivery person</Typography><Typography>{tracking.driver_name||'Not assigned yet'}</Typography>{tracking.driver_latitude?<><Alert severity="success" sx={{my:2}}>Live location received · Updated {date(tracking.location_updated_at!)}</Alert><Button variant="contained" href={mapUrl} target="_blank" startIcon={<NearMeOutlined/>}>View live location in Google Maps</Button></>:<Alert severity="info" sx={{mt:2}}>{tracking.status==='dispatched'?'Waiting for the delivery person’s GPS update.':'Live tracking begins when delivery starts.'}</Alert>}</Paper>
      <Paper variant="outlined" sx={{p:3}}><Typography variant="h6" sx={{mb:2}}>Delivery progress</Typography><div className="order-timeline">{tracking.events.map(e=><div key={e.id}><span className="timeline-dot"/><strong>{e.status.replaceAll('_',' ')}</strong><span>{date(e.created_at)}</span>{e.note&&<small>{e.note}</small>}</div>)}</div></Paper>
    </Stack>}
  </Container>
}
