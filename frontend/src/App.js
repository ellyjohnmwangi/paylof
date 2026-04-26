import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Barcode,
  BarChart3,
  Boxes,
  LogOut,
  Menu,
  RefreshCw,
  Search,
  ShoppingCart,
  Truck,
  UsersRound,
} from 'lucide-react';
import './App.css';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://127.0.0.1:8000/api';
const OFFLINE_QUEUE_KEY = 'PAYLOFT_offline_sales';
const AUTH_STORAGE_KEY = 'PAYLOFT_auth';
const MPESA_TERMINAL_STATUSES = ['PAID', 'FAILED', 'CANCELLED', 'TIMEOUT'];
const fallbackReportPlans = [
  { plan: 'daily', label: 'Daily', amount: 30, duration_days: 1 },
  { plan: 'weekly', label: 'Weekly', amount: 180, duration_days: 7 },
  { plan: 'monthly', label: 'Monthly', amount: 700, duration_days: 30 },
];

const tabs = ['All', 'Grocery', 'Drinks', 'Household', 'Low Stock'];
const visualCycle = ['shorts', 'shoe', 'wallet', 'bracelet', 'bag', 'flat', 'glasses'];
const salesReportTypes = [
  ['daily', 'Daily sales'],
  ['weekly', 'Weekly sales'],
  ['monthly', 'Monthly sales'],
  ['date_range', 'Sales by date range'],
  ['product', 'Sales by product'],
  ['payment_method', 'Sales by payment method'],
  ['cashier', 'Sales by cashier'],
];
const stockReportTypes = [
  ['current_stock', 'Current stock'],
  ['low_stock', 'Low stock'],
  ['out_of_stock', 'Out of stock'],
  ['stock_movement', 'Stock movement'],
  ['stock_adjustment', 'Stock adjustment'],
  ['damaged_lost_stock', 'Damaged/lost stock'],
];
const paymentReportTypes = [
  ['cash_payments', 'Cash payments'],
  ['mpesa_payments', 'M-Pesa payments'],
  ['payment_trends', 'Payment trends'],
];
const reportGroups = [
  ['inventory', 'Inventory'],
  ['sales', 'Sales'],
  ['payments', 'Payments'],
  ['distributors', 'Distributors'],
];

const copy = {
  saleComplete: 'Sale complete',
  saleQueued: 'Sale queued for sync',
  syncComplete: 'Offline sales synced',
  loadError: 'Backend offline. Local checkout is still ready.',
  saleError: 'Sale could not be completed.',
  cartEmpty: 'Add items before completing a sale.',
  mpesaPhoneRequired: 'Enter a phone number for M-Pesa.',
  mpesaUnavailableOffline: 'M-Pesa needs an online backend connection.',
  mpesaPromptSent: 'STK Push sent. Ask customer to enter M-Pesa PIN.',
  mpesaPending: 'Waiting for M-Pesa confirmation.',
  mpesaPaid: 'M-Pesa payment received.',
  mpesaFailed: 'M-Pesa payment was not completed.',
  mpesaCancelled: 'Payment was cancelled by the user.',
  mpesaTimeout: 'Payment timed out. Please try again.',
  reportsLocked: 'Choose a report plan to unlock this workspace.',
  reportsUnlocked: 'Reports unlocked',
  reportPaymentCancelled: 'Report payment was cancelled. You can try again.',
  reportPaymentTimeout: 'Report payment timed out. Please try again.',
  reportPhoneRequired: 'Enter an M-Pesa number for the report plan.',
  reportStkSent: 'STK Push sent for report access.',
  authError: 'Could not sign in. Check the details and try again.',
  saved: 'Saved',
};

const fallbackProducts = [
  { id: 'demo-1', name: 'Bread', price: '50.00', stock: 18, low_stock_threshold: 5 },
  { id: 'demo-2', name: 'Milk 500ml', price: '65.00', stock: 9, low_stock_threshold: 4 },
  { id: 'demo-3', name: 'Sugar 1kg', price: '180.00', stock: 6, low_stock_threshold: 3 },
  { id: 'demo-4', name: 'Cooking Oil', price: '260.00', stock: 4, low_stock_threshold: 3 },
  { id: 'demo-5', name: 'Airtime', price: '100.00', stock: 30, low_stock_threshold: 5 },
  { id: 'demo-6', name: 'Water 1L', price: '70.00', stock: 2, low_stock_threshold: 4 },
];

function readJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) || fallback;
  } catch (error) {
    return fallback;
  }
}

function readQueuedSales() {
  return readJson(OFFLINE_QUEUE_KEY, []);
}

function persistQueuedSales(sales) {
  localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(sales));
}

function readAuth() {
  return readJson(AUTH_STORAGE_KEY, null);
}

function persistAuth(auth) {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
}

function clearAuth() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

function money(value) {
  return `KES ${Number(value || 0).toFixed(0)}`;
}

function formatDateTime(value) {
  if (!value) return '';
  return new Intl.DateTimeFormat('en-KE', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

function formatDate(value) {
  if (!value) return '';
  return new Intl.DateTimeFormat('en-KE', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(value));
}

function saleReference() {
  return `local-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function calculateTransactionFee(subtotal) {
  if (subtotal <= 0) return 0;
  if (subtotal <= 500) return 2;
  if (subtotal <= 2000) return 3;
  return 5;
}

function mpesaTerminalMessage(status, fallback, isReport = false) {
  if (status === 'CANCELLED') {
    return isReport ? copy.reportPaymentCancelled : copy.mpesaCancelled;
  }
  if (status === 'TIMEOUT') {
    return isReport ? copy.reportPaymentTimeout : copy.mpesaTimeout;
  }
  if (status === 'FAILED') {
    return fallback || copy.mpesaFailed;
  }
  return fallback || copy.mpesaFailed;
}

function Icon({ name }) {
  const icons = {
    barcode: Barcode,
    checkout: ShoppingCart,
    distributors: Truck,
    inventory: Boxes,
    logout: LogOut,
    menu: Menu,
    reports: BarChart3,
    search: Search,
    sync: RefreshCw,
    users: UsersRound,
  };
  const LucideIcon = icons[name] || Menu;

  return (
    <LucideIcon aria-hidden="true" strokeWidth={1.8} />
  );
}

const fieldLabels = {
  business_name: 'Business name',
  contact_person: 'Contact person',
  customer_phone: 'Customer phone',
  distributor: 'Distributor',
  email: 'Email address',
  first_name: 'First name',
  is_active: 'Status',
  last_name: 'Last name',
  location: 'Location',
  low_stock_threshold: 'Reorder level',
  movement_type: 'Stock movement type',
  name: 'Name',
  non_field_errors: 'Form',
  notes: 'Notes',
  password: 'Password',
  phone: 'Phone number',
  phone_number: 'M-Pesa phone',
  price: 'Selling price',
  product: 'Product',
  quantity: 'Quantity',
  role: 'Role',
  stock: 'Opening stock',
  username: 'Username',
};

function fieldLabel(field) {
  return fieldLabels[field] || field.replaceAll('_', ' ');
}

function stringifyError(value) {
  if (Array.isArray(value)) return value.map(stringifyError).filter(Boolean).join(' ');
  if (value && typeof value === 'object') return Object.values(value).map(stringifyError).filter(Boolean).join(' ');
  return value ? String(value) : '';
}

async function readApiError(response) {
  const body = await response.json().catch(() => ({}));
  const fields = {};
  let message = '';

  Object.entries(body).forEach(([field, value]) => {
    const text = stringifyError(value);
    if (!text) return;
    if (field === 'detail') {
      message = text;
      return;
    }
    fields[field] = text;
  });

  const [firstField, firstMessage] = Object.entries(fields)[0] || [];
  if (!message && firstField) message = `${fieldLabel(firstField)}: ${firstMessage}`;

  return {
    fields,
    message: message || copy.saleError,
  };
}

function FormField({ error, children }) {
  return (
    <label className={`form-field ${error ? 'invalid' : ''}`}>
      {children}
      {error && <span className="field-error">{error}</span>}
    </label>
  );
}

function ProductThumb({ type }) {
  return (
    <div className={`product-thumb ${type}`} aria-hidden="true">
      <span />
    </div>
  );
}

function App() {
  const [auth, setAuth] = useState(readAuth);
  const [authMode, setAuthMode] = useState('login');
  const [authForm, setAuthForm] = useState({
    username: 'admin',
    password: 'admin123',
    business_name: 'My SME Shop',
    email: '',
  });
  const [products, setProducts] = useState([]);
  const [distributors, setDistributors] = useState([]);
  const [team, setTeam] = useState([]);
  const [cart, setCart] = useState([]);
  const [sales, setSales] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [salesReport, setSalesReport] = useState(null);
  const [stockReport, setStockReport] = useState(null);
  const [reportAccess, setReportAccess] = useState(null);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);
  const [subscriptionPurchasing, setSubscriptionPurchasing] = useState('');
  const [selectedReportPlan, setSelectedReportPlan] = useState('');
  const [reportPhone, setReportPhone] = useState('');
  const [reportPayment, setReportPayment] = useState(null);
  const [offlineQueue, setOfflineQueue] = useState(readQueuedSales);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [customerPhone, setCustomerPhone] = useState('');
  const [pendingMpesa, setPendingMpesa] = useState(null);
  const mpesaPollTimer = useRef(null);
  const reportPollTimer = useRef(null);
  const [activeTab, setActiveTab] = useState('All');
  const [activePanel, setActivePanel] = useState(() => {
    const storedAuth = readAuth();
    const storedCapabilities = storedAuth?.user?.profile?.capabilities || [];
    return storedCapabilities.includes('reports') && storedCapabilities.includes('inventory')
      ? 'inventory'
      : 'checkout';
  });
  const [adminMenuCollapsed, setAdminMenuCollapsed] = useState(false);
  const [reportsMenuOpen, setReportsMenuOpen] = useState(false);
  const [adminReportGroup, setAdminReportGroup] = useState('sales');
  const [searchTerm, setSearchTerm] = useState('');
  const [inventorySearch, setInventorySearch] = useState('');
  const [userSearch, setUserSearch] = useState('');
  const [distributorSearch, setDistributorSearch] = useState('');
  const [salesReportType, setSalesReportType] = useState('daily');
  const [stockReportType, setStockReportType] = useState('current_stock');
  const [paymentReportType, setPaymentReportType] = useState('cash_payments');
  const [reportDates, setReportDates] = useState({ start_date: '', end_date: '' });
  const [discount, setDiscount] = useState(0);
  const [productForm, setProductForm] = useState({
    name: '',
    price: '',
    stock: '',
    low_stock_threshold: '5',
    distributor: '',
  });
  const [distributorForm, setDistributorForm] = useState({
    name: '',
    contact_person: '',
    phone: '',
    email: '',
    location: '',
    notes: '',
  });
  const [userForm, setUserForm] = useState({
    username: '',
    email: '',
    password: '',
    role: 'cashier',
    phone: '',
    is_active: true,
  });
  const [stockAction, setStockAction] = useState({
    product: '',
    movement_type: 'added',
    quantity: '',
    note: '',
  });
  const [selectedUserId, setSelectedUserId] = useState('');
  const [selectedDistributorId, setSelectedDistributorId] = useState('');
  const [selectedProductId, setSelectedProductId] = useState('');
  const [userEditForm, setUserEditForm] = useState({
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    role: 'cashier',
    phone: '',
    is_active: true,
  });
  const [distributorEditForm, setDistributorEditForm] = useState({
    name: '',
    contact_person: '',
    phone: '',
    email: '',
    location: '',
    notes: '',
  });
  const [productEditForm, setProductEditForm] = useState({
    name: '',
    price: '',
    stock: '',
    low_stock_threshold: '5',
    distributor: '',
  });

  const capabilities = useMemo(
    () => auth?.user?.profile?.capabilities || [],
    [auth]
  );
  const can = useCallback((capability) => capabilities.includes(capability), [capabilities]);
  const role = auth?.user?.profile?.role || '';
  const businessName = auth?.user?.profile?.business?.name || 'PAYLOFT';
  const isAdmin = can('reports');
  const reportPlans = reportAccess?.plans || fallbackReportPlans;
  const hasReportSubscription = Boolean(reportAccess?.has_active_subscription);
  const activeReportSubscription = reportAccess?.active_subscription;
  const selectedUser = team.find((member) => String(member.id) === String(selectedUserId));
  const selectedDistributor = distributors.find((distributor) => String(distributor.id) === String(selectedDistributorId));
  const selectedProduct = products.find((product) => String(product.id) === String(selectedProductId));
  const selectedDistributorProducts = products.filter(
    (product) => String(product.distributor) === String(selectedDistributorId)
  );

  const showMessage = useCallback((text, type = 'success') => {
    setMessage({ text, type });
    window.clearTimeout(showMessage.timer);
    showMessage.timer = window.setTimeout(() => setMessage(null), 3200);
  }, []);

  const apiRequest = useCallback(async (path, options = {}) => {
    const headers = {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(auth?.token ? { Authorization: `Token ${auth.token}` } : {}),
      ...options.headers,
    };
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (response.status === 401) {
      clearAuth();
      setAuth(null);
    }
    return response;
  }, [auth]);

  const parseError = useCallback(async (response) => {
    const error = await readApiError(response);
    return error.message;
  }, []);

  const setFormErrors = useCallback((scope, errors = {}) => {
    setFieldErrors((current) => {
      const next = Object.fromEntries(
        Object.entries(current).filter(([key]) => !key.startsWith(`${scope}.`))
      );
      Object.entries(errors).forEach(([field, text]) => {
        if (text) next[`${scope}.${field}`] = text;
      });
      return next;
    });
  }, []);

  const clearFormErrors = useCallback((scope) => {
    setFormErrors(scope, {});
  }, [setFormErrors]);

  const clearFieldError = useCallback((scope, field) => {
    setFieldErrors((current) => {
      const key = `${scope}.${field}`;
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }, []);

  const fieldError = useCallback((scope, field) => fieldErrors[`${scope}.${field}`] || '', [fieldErrors]);

  const updateFormField = useCallback((scope, setter, field, value) => {
    clearFieldError(scope, field);
    setter((current) => ({ ...current, [field]: value }));
  }, [clearFieldError]);

  const formErrorMessage = useCallback(async (scope, response, fallback = copy.saleError) => {
    const error = await readApiError(response);
    setFormErrors(scope, error.fields);
    return error.message || fallback;
  }, [setFormErrors]);

  const fetchProducts = useCallback(async () => {
    if (!auth) return;
    setLoading(true);
    try {
      const response = await apiRequest('/products/');
      if (!response.ok) throw new Error(await parseError(response));
      const data = await response.json();
      setProducts(Array.isArray(data) ? data : data.results || []);
    } catch (error) {
      showMessage(error.message || copy.loadError, 'error');
    } finally {
      setLoading(false);
    }
  }, [apiRequest, auth, parseError, showMessage]);

  const fetchSales = useCallback(async () => {
    if (!auth) return;
    try {
      const response = await apiRequest('/sales/');
      if (!response.ok) return;
      const data = await response.json();
      setSales((Array.isArray(data) ? data : data.results || []).slice(0, 3));
    } catch (error) {
      setSales([]);
    }
  }, [apiRequest, auth]);

  const fetchAnalytics = useCallback(async () => {
    if (!auth || !can('reports')) return;
    try {
      const response = await apiRequest('/sales/analytics/');
      if (response.status === 402) {
        const data = await response.json().catch(() => null);
        if (data) setReportAccess(data);
        setAnalytics(null);
        return;
      }
      if (!response.ok) return;
      setAnalytics(await response.json());
    } catch (error) {
      setAnalytics(null);
    }
  }, [apiRequest, auth, can]);

  const fetchReportAccess = useCallback(async () => {
    if (!auth || !can('reports')) return;
    setSubscriptionLoading(true);
    try {
      const response = await apiRequest('/reports/subscription/');
      if (!response.ok) return;
      setReportAccess(await response.json());
    } catch (error) {
      setReportAccess(null);
    } finally {
      setSubscriptionLoading(false);
    }
  }, [apiRequest, auth, can]);

  const reportQuery = useCallback((type) => {
    const params = new URLSearchParams({ type });
    if (reportDates.start_date) params.set('start_date', reportDates.start_date);
    if (reportDates.end_date) params.set('end_date', reportDates.end_date);
    return params.toString();
  }, [reportDates]);
  const activeSalesReportType = adminReportGroup === 'payments' ? paymentReportType : salesReportType;

  const fetchReports = useCallback(async () => {
    if (!auth || !can('reports')) return;
    try {
      const [salesResponse, stockResponse] = await Promise.all([
        apiRequest(`/sales/reports/?${reportQuery(activeSalesReportType)}`),
        apiRequest(`/products/reports/?${reportQuery(stockReportType)}`),
      ]);
      const lockedResponse = [salesResponse, stockResponse].find((response) => response.status === 402);
      if (lockedResponse) {
        const data = await lockedResponse.json().catch(() => null);
        if (data) setReportAccess(data);
        setSalesReport(null);
        setStockReport(null);
        return;
      }
      if (salesResponse.ok) setSalesReport(await salesResponse.json());
      if (stockResponse.ok) setStockReport(await stockResponse.json());
    } catch (error) {
      setSalesReport(null);
      setStockReport(null);
    }
  }, [activeSalesReportType, apiRequest, auth, can, reportQuery, stockReportType]);

  const pollReportSubscriptionPayment = useCallback((paymentId) => {
    if (!paymentId) return;

    window.clearTimeout(reportPollTimer.current);
    let attempts = 0;

    const run = async () => {
      attempts += 1;

      try {
        const response = await apiRequest(`/reports/subscription/payment-status/${paymentId}/`);
        if (!response.ok) throw new Error(await parseError(response));
        const data = await response.json();
        console.log('PAYMENT STATUS:', data);
        const payment = data.payment;
        const status = payment?.status || 'PENDING';

        setReportAccess(data);
        setReportPayment(payment || null);

        if (data.has_active_subscription || status === 'PAID') {
          showMessage(copy.reportsUnlocked);
          fetchReports();
          fetchAnalytics();
          return;
        }

        if (MPESA_TERMINAL_STATUSES.includes(status)) {
          showMessage(
            mpesaTerminalMessage(status, payment?.result_description || 'Report payment was not completed.', true),
            'error'
          );
          return;
        }

        if (attempts < 20) {
          reportPollTimer.current = window.setTimeout(run, 3000);
        } else {
          const timeoutPayment = {
            ...(payment || { payment_id: paymentId }),
            status: 'TIMEOUT',
            result_description: copy.reportPaymentTimeout,
          };
          setReportPayment(timeoutPayment);
          showMessage(copy.reportPaymentTimeout, 'error');
        }
      } catch (error) {
        if (attempts < 5) {
          reportPollTimer.current = window.setTimeout(run, 3000);
        } else {
          showMessage(error.message || copy.saleError, 'error');
        }
      }
    };

    run();
  }, [apiRequest, fetchAnalytics, fetchReports, parseError, showMessage]);

  const purchaseReportSubscription = useCallback(async (plan) => {
    if (!auth || !can('reports')) return;
    if (!reportPhone.trim()) {
      setFormErrors('report', { phone_number: copy.reportPhoneRequired });
      showMessage(copy.reportPhoneRequired, 'error');
      return;
    }

    clearFormErrors('report');
    setSubscriptionPurchasing(plan);

    try {
      const response = await apiRequest('/reports/subscription/', {
        method: 'POST',
        body: JSON.stringify({ plan, phone_number: reportPhone.trim() }),
      });
      if (!response.ok) throw new Error(await formErrorMessage('report', response));
      const data = await response.json();
      setReportAccess(data);
      setReportPayment(data.payment || null);
      console.log('PAYMENT ID:', data.payment_id || data.payment?.payment_id);
      showMessage(copy.reportStkSent);
      pollReportSubscriptionPayment(data.payment_id || data.payment?.payment_id);
    } catch (error) {
      showMessage(error.message || copy.saleError, 'error');
    } finally {
      setSubscriptionPurchasing('');
    }
  }, [apiRequest, auth, can, clearFormErrors, formErrorMessage, pollReportSubscriptionPayment, reportPhone, setFormErrors, showMessage]);

  const fetchDistributors = useCallback(async () => {
    if (!auth || (!can('distributors') && !can('inventory'))) return;
    try {
      const response = await apiRequest('/distributors/');
      if (!response.ok) return;
      const data = await response.json();
      setDistributors(Array.isArray(data) ? data : data.results || []);
    } catch (error) {
      setDistributors([]);
    }
  }, [apiRequest, auth, can]);

  const fetchTeam = useCallback(async () => {
    if (!auth || !can('users')) return;
    try {
      const response = await apiRequest('/users/');
      if (!response.ok) return;
      const data = await response.json();
      setTeam(Array.isArray(data) ? data : data.results || []);
    } catch (error) {
      setTeam([]);
    }
  }, [apiRequest, auth, can]);

  const refreshWorkspace = useCallback(() => {
    fetchProducts();
    fetchSales();
    fetchAnalytics();
    fetchReportAccess();
    fetchReports();
    fetchDistributors();
    fetchTeam();
  }, [fetchAnalytics, fetchDistributors, fetchProducts, fetchReportAccess, fetchReports, fetchSales, fetchTeam]);

  useEffect(() => {
    if (auth) refreshWorkspace();
  }, [auth, refreshWorkspace]);

  useEffect(() => {
    if (auth && isAdmin && activePanel === 'checkout') {
      setActivePanel('inventory');
    }
  }, [activePanel, auth, isAdmin]);

  useEffect(() => {
    if (activePanel !== 'reports') setReportsMenuOpen(false);
  }, [activePanel]);

  useEffect(() => {
    if (auth && isAdmin) fetchReports();
  }, [auth, fetchReports, isAdmin]);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => () => {
    window.clearTimeout(mpesaPollTimer.current);
    window.clearTimeout(reportPollTimer.current);
  }, []);

  const catalog = useMemo(() => {
    const source = products.length > 0 ? products : fallbackProducts;
    return source.map((product, index) => ({
      ...product,
      visual: visualCycle[index % visualCycle.length],
      category: tabs[index % tabs.length],
      isDemo: String(product.id).startsWith('demo-'),
    }));
  }, [products]);

  const filteredProducts = useMemo(() => {
    const search = searchTerm.trim().toLowerCase();
    return catalog.filter((product) => {
      const matchesSearch = !search || product.name.toLowerCase().includes(search);
      const matchesTab =
        activeTab === 'All' ||
        product.category === activeTab ||
        (activeTab === 'Low Stock' && Number(product.stock) <= Number(product.low_stock_threshold || 3));
      return matchesSearch && matchesTab;
    });
  }, [activeTab, catalog, searchTerm]);
  const productSuggestions = useMemo(() => {
    const search = searchTerm.trim().toLowerCase();
    if (!search) return [];
    return catalog
      .filter((product) => product.name.toLowerCase().includes(search))
      .slice(0, 6);
  }, [catalog, searchTerm]);
  const filteredInventoryProducts = useMemo(() => {
    const search = inventorySearch.trim().toLowerCase();
    if (!search) return products;
    return products.filter((product) => (
      product.name.toLowerCase().includes(search) ||
      String(product.distributor_name || '').toLowerCase().includes(search)
    ));
  }, [inventorySearch, products]);
  const inventorySuggestions = useMemo(() => filteredInventoryProducts.slice(0, 6), [filteredInventoryProducts]);
  const filteredTeam = useMemo(() => {
    const search = userSearch.trim().toLowerCase();
    if (!search) return team;
    return team.filter((member) => (
      member.username.toLowerCase().includes(search) ||
      String(member.email || '').toLowerCase().includes(search) ||
      String(member.role || '').toLowerCase().includes(search) ||
      String(member.phone || '').toLowerCase().includes(search)
    ));
  }, [team, userSearch]);
  const userSuggestions = useMemo(() => filteredTeam.slice(0, 6), [filteredTeam]);
  const filteredDistributors = useMemo(() => {
    const search = distributorSearch.trim().toLowerCase();
    if (!search) return distributors;
    return distributors.filter((distributor) => (
      distributor.name.toLowerCase().includes(search) ||
      String(distributor.contact_person || '').toLowerCase().includes(search) ||
      String(distributor.phone || '').toLowerCase().includes(search) ||
      String(distributor.location || '').toLowerCase().includes(search)
    ));
  }, [distributorSearch, distributors]);
  const distributorSuggestions = useMemo(() => filteredDistributors.slice(0, 6), [filteredDistributors]);

  const cartSubtotal = useMemo(
    () => cart.reduce((sum, item) => sum + Number(item.product.price) * item.quantity, 0),
    [cart]
  );
  const visibleSubtotal = cartSubtotal;
  const transactionFee = calculateTransactionFee(visibleSubtotal);
  const totalDue = Math.max(0, visibleSubtotal + transactionFee - discount);
  const cartRows = cart.map((item, index) => ({
        id: item.product.id,
        name: item.product.name,
        detail: `Stock: ${item.product.stock}`,
        quantity: item.quantity,
        price: Number(item.product.price) * item.quantity,
        visual: item.product.visual || visualCycle[index % visualCycle.length],
        live: true,
      }));

  const handleAuth = async (event) => {
    event.preventDefault();
    const endpoint = authMode === 'login' ? '/auth/login/' : '/auth/register/';
    const payload = authMode === 'login'
      ? { username: authForm.username, password: authForm.password }
      : authForm;

    try {
      clearFormErrors('auth');
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await formErrorMessage('auth', response, copy.authError));
      const data = await response.json();
      const loginCapabilities = data.user?.profile?.capabilities || [];
      setAuth(data);
      persistAuth(data);
      setActivePanel(loginCapabilities.includes('reports') && loginCapabilities.includes('inventory') ? 'inventory' : 'checkout');
      showMessage(`Signed in as ${data.user.username}`);
    } catch (error) {
      showMessage(error.message || copy.authError, 'error');
    }
  };

  const logout = async () => {
    if (auth?.token) {
      await apiRequest('/auth/logout/', { method: 'POST' }).catch(() => {});
    }
    clearAuth();
    setAuth(null);
    setProducts([]);
    setCart([]);
    setAnalytics(null);
    setSalesReport(null);
    setStockReport(null);
    setActivePanel('checkout');
  };

  const postSale = useCallback(async (payload) => {
    const response = await apiRequest('/sales/create_sale/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const apiError = await readApiError(response);
      const error = new Error(apiError.message);
      error.fields = apiError.fields;
      throw error;
    }

    return response.json();
  }, [apiRequest]);

  const pollMpesaPayment = useCallback((paymentId) => {
    if (!paymentId) return;

    window.clearTimeout(mpesaPollTimer.current);
    let attempts = 0;

    const run = async () => {
      attempts += 1;

      try {
        const response = await apiRequest(`/mpesa/payment-status/${paymentId}/`);
        if (!response.ok) throw new Error(await parseError(response));
        const data = await response.json();
        console.log('PAYMENT STATUS:', data);
        const status = data.status || 'PENDING';
        const description = data.result_description || data.customer_message || copy.mpesaPending;

        setPendingMpesa({
          paymentId: data.payment_id,
          saleId: data.sale_id,
          status,
          description,
          receipt: data.mpesa_receipt_number,
        });

        if (status === 'PAID') {
          showMessage(`${copy.mpesaPaid} ${data.mpesa_receipt_number || ''}`.trim());
          refreshWorkspace();
          return;
        }

        if (MPESA_TERMINAL_STATUSES.includes(status)) {
          showMessage(mpesaTerminalMessage(status, description), 'error');
          refreshWorkspace();
          return;
        }

        if (attempts < 20) {
          mpesaPollTimer.current = window.setTimeout(run, 3000);
        } else {
          setPendingMpesa((current) => ({
            ...(current || { paymentId }),
            status: 'TIMEOUT',
            description: copy.mpesaTimeout,
          }));
          showMessage(copy.mpesaTimeout, 'error');
          refreshWorkspace();
        }
      } catch (error) {
        if (attempts < 5) {
          mpesaPollTimer.current = window.setTimeout(run, 3000);
        } else {
          showMessage(error.message || copy.saleError, 'error');
        }
      }
    };

    run();
  }, [apiRequest, parseError, refreshWorkspace, showMessage]);

  const syncQueuedSales = useCallback(async () => {
    if (!isOnline || offlineQueue.length === 0 || !auth) return;

    const remaining = [];
    let syncedCount = 0;

    for (const queuedSale of offlineQueue) {
      try {
        await postSale(queuedSale.payload);
        syncedCount += 1;
      } catch (error) {
        remaining.push(queuedSale);
      }
    }

    setOfflineQueue(remaining);
    persistQueuedSales(remaining);

    if (syncedCount > 0) {
      showMessage(copy.syncComplete);
      refreshWorkspace();
    }
  }, [auth, isOnline, offlineQueue, postSale, refreshWorkspace, showMessage]);

  useEffect(() => {
    syncQueuedSales();
  }, [syncQueuedSales]);

  const addToCart = (product) => {
    if (!can('sales') || product.stock <= 0) return;

    setCart((current) => {
      const existing = current.find((item) => item.product.id === product.id);
      const currentQuantity = existing ? existing.quantity : 0;
      if (currentQuantity >= product.stock) return current;

      if (existing) {
        return current.map((item) =>
          item.product.id === product.id ? { ...item, quantity: item.quantity + 1 } : item
        );
      }

      return [...current, { product, quantity: 1 }];
    });
  };

  const decreaseItem = (productId) => {
    setCart((current) =>
      current
        .map((item) =>
          item.product.id === productId ? { ...item, quantity: item.quantity - 1 } : item
        )
        .filter((item) => item.quantity > 0)
    );
  };

  const removeFromCart = (productId) => {
    setCart((current) => current.filter((item) => item.product.id !== productId));
  };

  const queueSale = (payload) => {
    const entry = {
      id: payload.offline_reference,
      payload,
      total: totalDue,
      created_at: new Date().toISOString(),
    };

    setOfflineQueue((current) => {
      const next = [...current, entry];
      persistQueuedSales(next);
      return next;
    });

    setCart([]);
    showMessage(copy.saleQueued);
  };

  const createSale = async () => {
    if (cart.length === 0) {
      showMessage(copy.cartEmpty, 'error');
      return;
    }

    if (paymentMethod === 'mpesa' && !customerPhone.trim()) {
      setFormErrors('checkout', { customer_phone: copy.mpesaPhoneRequired });
      showMessage(copy.mpesaPhoneRequired, 'error');
      return;
    }

    if (paymentMethod === 'mpesa' && (!isOnline || cart.some((item) => item.product.isDemo))) {
      showMessage(copy.mpesaUnavailableOffline, 'error');
      return;
    }

    const payload = {
      items: cart.map((item) => ({
        product_id: item.product.id,
        quantity: item.quantity,
      })),
      payment_method: paymentMethod,
      customer_phone: paymentMethod === 'mpesa' ? customerPhone.trim() : '',
      offline_reference: saleReference(),
    };

    if (!isOnline || cart.some((item) => item.product.isDemo)) {
      queueSale(payload);
      return;
    }

    setSubmitting(true);
    clearFormErrors('checkout');

    try {
      const sale = await postSale(payload);
      if (paymentMethod === 'mpesa') {
        const payment = sale.mpesa_payment;
        console.log('PAYMENT ID:', sale.payment_id || payment?.payment_id);
        setPendingMpesa({
          paymentId: sale.payment_id || payment?.payment_id,
          saleId: sale.id,
          status: payment?.status || 'PENDING',
          description: payment?.customer_message || copy.mpesaPending,
          receipt: payment?.mpesa_receipt_number,
        });
        showMessage(copy.mpesaPromptSent);
        pollMpesaPayment(sale.payment_id || payment?.payment_id);
      } else {
        showMessage(`${copy.saleComplete}: ${money(sale.total_amount)}`);
      }
      setCart([]);
      setCustomerPhone('');
      refreshWorkspace();
    } catch (error) {
      if (error.name === 'TypeError' && paymentMethod !== 'mpesa') {
        queueSale(payload);
      } else {
        if (error.fields) setFormErrors('checkout', error.fields);
        showMessage(error.message || copy.saleError, 'error');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const createProduct = async (event) => {
    event.preventDefault();
    if (!can('inventory')) return;

    const payload = {
      ...productForm,
      stock: Number(productForm.stock || 0),
      low_stock_threshold: Number(productForm.low_stock_threshold || 5),
      distributor: productForm.distributor || null,
    };

    try {
      clearFormErrors('product');
      const response = await apiRequest('/products/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await formErrorMessage('product', response));
      setProductForm({ name: '', price: '', stock: '', low_stock_threshold: '5', distributor: '' });
      showMessage(copy.saved);
      refreshWorkspace();
    } catch (error) {
      showMessage(error.message || copy.saleError, 'error');
    }
  };

  const adjustStock = async (event) => {
    event.preventDefault();
    if (!can('inventory') || !stockAction.product) return;

    const payload = {
      movement_type: stockAction.movement_type,
      quantity: Number(stockAction.quantity || 0),
      note: stockAction.note,
    };

    try {
      clearFormErrors('stock');
      const response = await apiRequest(`/products/${stockAction.product}/adjust_stock/`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await formErrorMessage('stock', response));
      setStockAction({ product: '', movement_type: 'added', quantity: '', note: '' });
      showMessage(copy.saved);
      refreshWorkspace();
    } catch (error) {
      showMessage(error.message || copy.saleError, 'error');
    }
  };

  const createDistributor = async (event) => {
    event.preventDefault();
    if (!can('distributors')) return;

    try {
      clearFormErrors('distributor');
      const response = await apiRequest('/distributors/', {
        method: 'POST',
        body: JSON.stringify(distributorForm),
      });
      if (!response.ok) throw new Error(await formErrorMessage('distributor', response));
      setDistributorForm({ name: '', contact_person: '', phone: '', location: '', email: '', notes: '' });
      showMessage(copy.saved);
      fetchDistributors();
    } catch (error) {
      showMessage(error.message || copy.saleError, 'error');
    }
  };

  const createUser = async (event) => {
    event.preventDefault();
    if (!can('users')) return;

    try {
      clearFormErrors('user');
      const response = await apiRequest('/users/', {
        method: 'POST',
        body: JSON.stringify(userForm),
      });
      if (!response.ok) throw new Error(await formErrorMessage('user', response));
      setUserForm({ username: '', email: '', password: '', role: 'cashier', phone: '', is_active: true });
      showMessage(copy.saved);
      fetchTeam();
    } catch (error) {
      showMessage(error.message || copy.saleError, 'error');
    }
  };

  const selectUser = (member) => {
    if (String(selectedUserId) === String(member.id)) {
      setSelectedUserId('');
      return;
    }

    setSelectedUserId(member.id);
    setUserEditForm({
      username: member.username || '',
      email: member.email || '',
      first_name: member.first_name || '',
      last_name: member.last_name || '',
      role: member.role || 'cashier',
      phone: member.phone || '',
      is_active: Boolean(member.is_active),
    });
  };

  const updateUser = async (event) => {
    event.preventDefault();
    if (!can('users') || !selectedUser) return;

    try {
      clearFormErrors('userEdit');
      const response = await apiRequest(`/users/${selectedUser.id}/`, {
        method: 'PATCH',
        body: JSON.stringify(userEditForm),
      });
      if (!response.ok) throw new Error(await formErrorMessage('userEdit', response));
      showMessage(copy.saved);
      fetchTeam();
    } catch (error) {
      showMessage(error.message || copy.saleError, 'error');
    }
  };

  const deactivateUser = async () => {
    if (!can('users') || !selectedUser) return;

    try {
      const response = await apiRequest(`/users/${selectedUser.id}/`, { method: 'DELETE' });
      if (!response.ok) throw new Error(await parseError(response));
      showMessage(`${selectedUser.username} deactivated`);
      setSelectedUserId('');
      fetchTeam();
    } catch (error) {
      showMessage(error.message || copy.saleError, 'error');
    }
  };

  const sendPasswordReset = async () => {
    if (!can('users') || !selectedUser) return;

    try {
      const response = await apiRequest(`/users/${selectedUser.id}/send_password_reset/`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error(await parseError(response));
      const data = await response.json();
      showMessage(data.detail || 'Password reset link generated');
    } catch (error) {
      showMessage(error.message || copy.saleError, 'error');
    }
  };

  const selectDistributor = (distributor) => {
    if (String(selectedDistributorId) === String(distributor.id)) {
      setSelectedDistributorId('');
      return;
    }

    setSelectedDistributorId(distributor.id);
    setDistributorEditForm({
      name: distributor.name || '',
      contact_person: distributor.contact_person || '',
      phone: distributor.phone || '',
      email: distributor.email || '',
      location: distributor.location || '',
      notes: distributor.notes || '',
    });
  };

  const updateDistributor = async (event) => {
    event.preventDefault();
    if (!can('distributors') || !selectedDistributor) return;

    try {
      clearFormErrors('distributorEdit');
      const response = await apiRequest(`/distributors/${selectedDistributor.id}/`, {
        method: 'PATCH',
        body: JSON.stringify(distributorEditForm),
      });
      if (!response.ok) throw new Error(await formErrorMessage('distributorEdit', response));
      showMessage(copy.saved);
      fetchDistributors();
    } catch (error) {
      showMessage(error.message || copy.saleError, 'error');
    }
  };

  const removeDistributor = async () => {
    if (!can('distributors') || !selectedDistributor) return;

    try {
      const response = await apiRequest(`/distributors/${selectedDistributor.id}/`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error(await parseError(response));
      showMessage(`${selectedDistributor.name} removed`);
      setSelectedDistributorId('');
      refreshWorkspace();
    } catch (error) {
      showMessage(error.message || copy.saleError, 'error');
    }
  };

  const selectProduct = (product) => {
    setSelectedProductId(product.id);
    setProductEditForm({
      name: product.name || '',
      price: product.price || '',
      stock: product.stock || 0,
      low_stock_threshold: product.low_stock_threshold || 5,
      distributor: product.distributor || '',
    });
    setStockAction((current) => ({ ...current, product: product.id }));
  };

  const updateProduct = async (event) => {
    event.preventDefault();
    if (!can('inventory') || !selectedProduct) return;

    try {
      clearFormErrors('productEdit');
      const response = await apiRequest(`/products/${selectedProduct.id}/`, {
        method: 'PATCH',
        body: JSON.stringify({
          ...productEditForm,
          distributor: productEditForm.distributor || null,
          stock: Number(productEditForm.stock || 0),
          low_stock_threshold: Number(productEditForm.low_stock_threshold || 5),
        }),
      });
      if (!response.ok) throw new Error(await formErrorMessage('productEdit', response));
      showMessage(copy.saved);
      refreshWorkspace();
    } catch (error) {
      showMessage(error.message || copy.saleError, 'error');
    }
  };

  const renderReportPaywall = () => (
    <div className="report-paywall">
      <div className="paywall-copy">
        <strong>Reports are locked</strong>
        <span>{subscriptionLoading ? 'Checking subscription...' : copy.reportsLocked}</span>
      </div>
      <div className="pricing-grid">
        {reportPlans.map((plan) => {
          const duration = Number(plan.duration_days) === 1
            ? '24 hours'
            : `${plan.duration_days} days`;
          const isSelected = selectedReportPlan === plan.plan;
          return (
            <div
              key={plan.plan}
              className={`pricing-box ${isSelected ? 'selected' : ''}`}
            >
              <span>{plan.label}</span>
              <strong>{money(plan.amount)}</strong>
              <small>{duration}</small>
              {isSelected ? (
                <div className="pricing-pay-form">
                  <FormField error={fieldError('report', 'phone_number')}>
                    <input
                      value={reportPhone}
                      onChange={(event) => {
                        clearFieldError('report', 'phone_number');
                        setReportPhone(event.target.value);
                      }}
                      placeholder="e.g. 254712345678"
                      aria-invalid={Boolean(fieldError('report', 'phone_number'))}
                    />
                  </FormField>
                  <button
                    type="button"
                    onClick={() => purchaseReportSubscription(plan.plan)}
                    disabled={Boolean(subscriptionPurchasing)}
                  >
                    {subscriptionPurchasing === plan.plan ? 'Sending STK' : 'Pay'}
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className="pricing-select-button"
                  onClick={() => {
                    setSelectedReportPlan(plan.plan);
                    setReportPayment(null);
                  }}
                  disabled={Boolean(subscriptionPurchasing)}
                >
                  Choose plan
                </button>
              )}
              {isSelected && reportPayment && (
                <em>
                  {reportPayment.status === 'PENDING'
                    ? 'Waiting for PIN confirmation'
                    : mpesaTerminalMessage(reportPayment.status, reportPayment.result_description || reportPayment.status, true)}
                </em>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );

  const renderReportsPanel = () => (
    <>
      <div className="panel-heading">
        <h2>{reportGroups.find(([value]) => value === adminReportGroup)?.[1]} Reports</h2>
        <p>
          {hasReportSubscription && activeReportSubscription
            ? `Unlocked until ${formatDateTime(activeReportSubscription.expires_at)}`
            : activeReportLabel || 'Admin overview'}
        </p>
      </div>
      <div className={`report-paywall-shell ${hasReportSubscription ? '' : 'locked'}`}>
        <div className="report-content">
          <div className="report-controls contextual-report-controls">
            <input type="date" value={reportDates.start_date} onChange={(event) => setReportDates({ ...reportDates, start_date: event.target.value })} />
            <input type="date" value={reportDates.end_date} onChange={(event) => setReportDates({ ...reportDates, end_date: event.target.value })} />
            <button type="button" onClick={fetchReports}>Refresh</button>
          </div>
          {adminReportGroup === 'sales' && (
            <>
      <div className="report-grid">
        <div><span>Total sales amount</span><strong>{money(salesReport?.total_sales_amount || 0)}</strong></div>
        <div><span>Transactions</span><strong>{salesReport?.number_of_transactions || 0}</strong></div>
        <div><span>Average sale</span><strong>{money(salesReport?.average_transaction_value || 0)}</strong></div>
        <div><span>Report range</span><strong>{activeReportLabel}</strong></div>
      </div>
      <div className="report-grid compact-report-grid">
        <div><span>Cash sales</span><strong>{money(salesReport?.cash_vs_mpesa_sales?.cash?.total_sales_amount || 0)}</strong></div>
        <div><span>M-Pesa sales</span><strong>{money(salesReport?.cash_vs_mpesa_sales?.mpesa?.total_sales_amount || 0)}</strong></div>
      </div>
      <div className="report-columns">
        <div className="data-list report-list">
          <h3>Best-selling products</h3>
          {(salesReport?.best_selling_products || []).map((item) => (
            <div key={`best-${item.product__name}`}>
              <strong>{item.product__name}</strong>
              <span>{item.quantity_sold} sold - {money(item.revenue)}</span>
            </div>
          ))}
        </div>
        <div className="data-list report-list">
          <h3>Slow-selling products</h3>
          {(salesReport?.slow_selling_products || []).map((item) => (
            <div key={`slow-${item.product__name}`}>
              <strong>{item.product__name}</strong>
              <span>{item.quantity_sold} sold - {money(item.revenue)}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="data-list stock-report-list">
        <h3>Selected sales report</h3>
        {(salesReport?.breakdown || []).map((item, index) => {
          const label = item.product__name || item.payment_method || item.user__username || item.period || `Row ${index + 1}`;
          const detail = item.quantity_sold
            ? `${item.quantity_sold} sold - ${money(item.total_sales_amount)}`
            : `${item.number_of_transactions || 0} transactions - ${money(item.total_sales_amount)}`;
          return (
            <div key={`${label}-${index}`}>
              <strong>{label}</strong>
              <span>{detail}</span>
            </div>
          );
        })}
      </div>
            </>
          )}
          {adminReportGroup === 'payments' && (
            <>
      <div className="report-grid">
        <div><span>Total payment amount</span><strong>{money(salesReport?.total_sales_amount || 0)}</strong></div>
        <div><span>Transactions</span><strong>{salesReport?.number_of_transactions || 0}</strong></div>
        <div><span>Average payment</span><strong>{money(salesReport?.average_transaction_value || 0)}</strong></div>
        <div><span>Report view</span><strong>{paymentReportTypes.find(([value]) => value === paymentReportType)?.[1]}</strong></div>
      </div>
      <div className="report-grid compact-report-grid">
        <div><span>Cash payments</span><strong>{money(salesReport?.cash_vs_mpesa_sales?.cash?.total_sales_amount || 0)}</strong></div>
        <div><span>Cash transactions</span><strong>{salesReport?.cash_vs_mpesa_sales?.cash?.number_of_transactions || 0}</strong></div>
        <div><span>M-Pesa payments</span><strong>{money(salesReport?.cash_vs_mpesa_sales?.mpesa?.total_sales_amount || 0)}</strong></div>
        <div><span>M-Pesa transactions</span><strong>{salesReport?.cash_vs_mpesa_sales?.mpesa?.number_of_transactions || 0}</strong></div>
      </div>
      <div className="data-list stock-report-list">
        <h3>{paymentReportType === 'payment_trends' ? 'Payment trends' : 'Payment transactions by cashier'}</h3>
        {(salesReport?.breakdown || []).map((item, index) => {
          const period = item.period ? formatDate(item.period) : `Row ${index + 1}`;
          const method = item.payment_method === 'mpesa' ? 'M-Pesa' : 'Cash';
          const cashier = item.user__username ? ` - ${item.user__username}` : '';
          return (
            <div key={`${period}-${method}-${cashier}-${index}`}>
              <strong>{paymentReportType === 'payment_trends' ? `${period} - ${method}` : `${period}${cashier}`}</strong>
              <span>{item.number_of_transactions || 0} transactions - {money(item.total_sales_amount)}</span>
            </div>
          );
        })}
      </div>
            </>
          )}
          {adminReportGroup === 'inventory' && (
            <>
          <div className="report-grid">
            <div><span>Products</span><strong>{stockReport?.summary?.product_count || 0}</strong></div>
            <div><span>Items below reorder</span><strong>{stockReport?.summary?.items_below_reorder_level || 0}</strong></div>
            <div><span>Low stock</span><strong>{stockReport?.summary?.low_stock_count || 0}</strong></div>
            <div><span>Out of stock</span><strong>{stockReport?.summary?.out_of_stock_count || 0}</strong></div>
          </div>
          <div className="report-grid compact-report-grid">
            <div><span>Stock added</span><strong>{stockReport?.summary?.stock_added || 0}</strong></div>
            <div><span>Stock sold</span><strong>{stockReport?.summary?.stock_sold || 0}</strong></div>
            <div><span>Manual adjustments</span><strong>{stockReport?.summary?.stock_adjusted_manually || 0}</strong></div>
            <div><span>Damaged/lost</span><strong>{stockReport?.summary?.damaged_or_lost_stock || 0}</strong></div>
          </div>
      <div className="data-list stock-report-list">
        {(stockReport?.products || []).map((item) => (
          <div key={item.product_name}>
            <strong>{item.product_name}</strong>
            <span>Available {item.quantity_available} - Reorder {item.reorder_level} - Added {item.stock_added} - Sold {item.stock_sold} - Adjusted {item.stock_adjusted_manually}</span>
          </div>
        ))}
      </div>
            </>
          )}
          {adminReportGroup === 'distributors' && (
            <>
          <div className="report-grid">
            <div><span>Total distributors</span><strong>{distributors.length}</strong></div>
            <div><span>Linked products</span><strong>{distributors.reduce((sum, distributor) => sum + Number(distributor.product_count || 0), 0)}</strong></div>
          </div>
          <div className="data-list stock-report-list">
            {distributors.map((distributor) => (
              <div key={distributor.id}>
                <strong>{distributor.name}</strong>
                <span>{distributor.contact_person || 'No contact'} - {distributor.phone || 'No phone'} - {distributor.product_count || 0} products</span>
              </div>
            ))}
          </div>
            </>
          )}
        </div>
        {!hasReportSubscription && renderReportPaywall()}
      </div>
    </>
  );

  const renderInventoryPanel = () => (
    <>
      <div className="panel-heading">
        <h2>Inventory</h2>
        <p>{filteredInventoryProducts.length} of {products.length} products</p>
      </div>
      <div className="search-stack">
        <label className="search-field">
          <Icon name="search" />
          <input
            value={inventorySearch}
            onChange={(event) => setInventorySearch(event.target.value)}
            placeholder="Search inventory by product or distributor"
          />
          <Icon name="barcode" />
        </label>
        {inventorySearch.trim() && inventorySuggestions.length > 0 && (
          <div className="suggestions-list">
            {inventorySuggestions.map((product) => (
              <button key={product.id} type="button" onClick={() => {
                setInventorySearch(product.name);
                selectProduct(product);
              }}>
                <strong>{product.name}</strong>
                <span>{money(product.price)} - Stock {product.stock} - {product.distributor_name || 'No distributor'}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <form className="management-form" onSubmit={createProduct}>
        <FormField error={fieldError('product', 'name')}>
          <input value={productForm.name} onChange={(event) => updateFormField('product', setProductForm, 'name', event.target.value)} placeholder="e.g. Bread 400g" required aria-invalid={Boolean(fieldError('product', 'name'))} />
        </FormField>
        <FormField error={fieldError('product', 'price')}>
          <input type="number" step="0.01" min="0" value={productForm.price} onChange={(event) => updateFormField('product', setProductForm, 'price', event.target.value)} placeholder="Selling price in KES" required aria-invalid={Boolean(fieldError('product', 'price'))} />
        </FormField>
        <FormField error={fieldError('product', 'stock')}>
          <input type="number" min="0" value={productForm.stock} onChange={(event) => updateFormField('product', setProductForm, 'stock', event.target.value)} placeholder="Opening stock quantity" aria-invalid={Boolean(fieldError('product', 'stock'))} />
        </FormField>
        <FormField error={fieldError('product', 'low_stock_threshold')}>
          <input type="number" min="0" value={productForm.low_stock_threshold} onChange={(event) => updateFormField('product', setProductForm, 'low_stock_threshold', event.target.value)} placeholder="Reorder alert level" aria-invalid={Boolean(fieldError('product', 'low_stock_threshold'))} />
        </FormField>
        <FormField error={fieldError('product', 'distributor')}>
          <select value={productForm.distributor} onChange={(event) => updateFormField('product', setProductForm, 'distributor', event.target.value)} aria-invalid={Boolean(fieldError('product', 'distributor'))}>
            <option value="">No distributor</option>
            {distributors.map((distributor) => (
              <option key={distributor.id} value={distributor.id}>{distributor.name}</option>
            ))}
          </select>
        </FormField>
        <button type="submit">Add product</button>
      </form>
      <form className="management-form stock-action-form" onSubmit={adjustStock}>
        <FormField error={fieldError('stock', 'product')}>
          <select value={stockAction.product} onChange={(event) => updateFormField('stock', setStockAction, 'product', event.target.value)} required aria-invalid={Boolean(fieldError('stock', 'product'))}>
            <option value="">Select product</option>
            {products.map((product) => (
              <option key={product.id} value={product.id}>{product.name}</option>
            ))}
          </select>
        </FormField>
        <FormField error={fieldError('stock', 'movement_type')}>
          <select value={stockAction.movement_type} onChange={(event) => updateFormField('stock', setStockAction, 'movement_type', event.target.value)} aria-invalid={Boolean(fieldError('stock', 'movement_type'))}>
            <option value="added">Stock added</option>
            <option value="adjusted">Manual adjustment</option>
            <option value="damaged">Damaged stock</option>
            <option value="lost">Lost stock</option>
          </select>
        </FormField>
        <FormField error={fieldError('stock', 'quantity')}>
          <input type="number" min="1" value={stockAction.quantity} onChange={(event) => updateFormField('stock', setStockAction, 'quantity', event.target.value)} placeholder="Units to add or remove" required aria-invalid={Boolean(fieldError('stock', 'quantity'))} />
        </FormField>
        <FormField error={fieldError('stock', 'note')}>
          <input value={stockAction.note} onChange={(event) => updateFormField('stock', setStockAction, 'note', event.target.value)} placeholder="e.g. Restocked from supplier" aria-invalid={Boolean(fieldError('stock', 'note'))} />
        </FormField>
        <button type="submit">Update stock</button>
      </form>
      <div className="data-list">
        {filteredInventoryProducts.map((product) => (
          <button
            key={product.id}
            type="button"
            className={`data-row ${String(selectedProductId) === String(product.id) ? 'selected' : ''}`}
            onClick={() => selectProduct(product)}
          >
            <strong>{product.name}</strong>
            <span>{money(product.price)} - Stock {product.stock} - Reorder {product.low_stock_threshold} - {product.distributor_name || 'No distributor'}</span>
          </button>
        ))}
      </div>
      {selectedProduct && (
        <section className="detail-panel">
          <div className="panel-heading">
            <h3>{selectedProduct.name}</h3>
            <p>Inventory actions</p>
          </div>
          <form className="management-form" onSubmit={updateProduct}>
            <FormField error={fieldError('productEdit', 'name')}>
              <input value={productEditForm.name} onChange={(event) => updateFormField('productEdit', setProductEditForm, 'name', event.target.value)} placeholder="e.g. Bread 400g" required aria-invalid={Boolean(fieldError('productEdit', 'name'))} />
            </FormField>
            <FormField error={fieldError('productEdit', 'price')}>
              <input type="number" step="0.01" min="0" value={productEditForm.price} onChange={(event) => updateFormField('productEdit', setProductEditForm, 'price', event.target.value)} placeholder="Selling price in KES" required aria-invalid={Boolean(fieldError('productEdit', 'price'))} />
            </FormField>
            <FormField error={fieldError('productEdit', 'stock')}>
              <input type="number" min="0" value={productEditForm.stock} onChange={(event) => updateFormField('productEdit', setProductEditForm, 'stock', event.target.value)} placeholder="Current stock quantity" aria-invalid={Boolean(fieldError('productEdit', 'stock'))} />
            </FormField>
            <FormField error={fieldError('productEdit', 'low_stock_threshold')}>
              <input type="number" min="0" value={productEditForm.low_stock_threshold} onChange={(event) => updateFormField('productEdit', setProductEditForm, 'low_stock_threshold', event.target.value)} placeholder="Reorder alert level" aria-invalid={Boolean(fieldError('productEdit', 'low_stock_threshold'))} />
            </FormField>
            <FormField error={fieldError('productEdit', 'distributor')}>
              <select value={productEditForm.distributor} onChange={(event) => updateFormField('productEdit', setProductEditForm, 'distributor', event.target.value)} aria-invalid={Boolean(fieldError('productEdit', 'distributor'))}>
                <option value="">No distributor</option>
                {distributors.map((distributor) => (
                  <option key={distributor.id} value={distributor.id}>{distributor.name}</option>
                ))}
              </select>
            </FormField>
            <button type="submit">Save product</button>
          </form>
          <div className="action-strip">
            <button type="button" onClick={() => setStockAction({ product: selectedProduct.id, movement_type: 'added', quantity: '1', note: 'Stock received' })}>Prepare restock</button>
            <button type="button" onClick={() => setStockAction({ product: selectedProduct.id, movement_type: 'damaged', quantity: '1', note: 'Damaged stock' })}>Mark damaged</button>
            <button type="button" onClick={() => setStockAction({ product: selectedProduct.id, movement_type: 'lost', quantity: '1', note: 'Lost stock' })}>Mark lost</button>
          </div>
        </section>
      )}
    </>
  );

  const renderUsersPanel = () => (
    <>
      <div className="panel-heading">
        <h2>Users</h2>
        <p>{filteredTeam.length} of {team.length} members</p>
      </div>
      <div className="search-stack">
        <label className="search-field">
          <Icon name="search" />
          <input
            value={userSearch}
            onChange={(event) => setUserSearch(event.target.value)}
            placeholder="Search users by name, email, role, or phone"
          />
          <Icon name="users" />
        </label>
        {userSearch.trim() && userSuggestions.length > 0 && (
          <div className="suggestions-list">
            {userSuggestions.map((member) => (
              <button key={member.id} type="button" onClick={() => {
                setUserSearch(member.username);
                selectUser(member);
              }}>
                <strong>{member.username}</strong>
                <span>{member.role} - {member.email || 'No email'} - {member.is_active ? 'active' : 'disabled'}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <form className="management-form" onSubmit={createUser}>
        <FormField error={fieldError('user', 'username')}>
          <input value={userForm.username} onChange={(event) => updateFormField('user', setUserForm, 'username', event.target.value)} placeholder="e.g. cashier1" required aria-invalid={Boolean(fieldError('user', 'username'))} />
        </FormField>
        <FormField error={fieldError('user', 'email')}>
          <input type="email" value={userForm.email} onChange={(event) => updateFormField('user', setUserForm, 'email', event.target.value)} placeholder="e.g. cashier@shop.co.ke" aria-invalid={Boolean(fieldError('user', 'email'))} />
        </FormField>
        <FormField error={fieldError('user', 'password')}>
          <input type="password" value={userForm.password} onChange={(event) => updateFormField('user', setUserForm, 'password', event.target.value)} placeholder="Temporary password" required aria-invalid={Boolean(fieldError('user', 'password'))} />
        </FormField>
        <FormField error={fieldError('user', 'role')}>
          <select value={userForm.role} onChange={(event) => updateFormField('user', setUserForm, 'role', event.target.value)} aria-invalid={Boolean(fieldError('user', 'role'))}>
            <option value="cashier">Cashier</option>
            <option value="manager">Manager</option>
            {role === 'owner' && <option value="owner">Owner</option>}
          </select>
        </FormField>
        <button type="submit">Add user</button>
      </form>
      <div className="data-list">
        {filteredTeam.map((member) => (
          <button
            key={member.id}
            type="button"
            className={`data-row ${String(selectedUserId) === String(member.id) ? 'selected' : ''}`}
            onClick={() => selectUser(member)}
          >
            <strong>{member.username}</strong>
            <span>{member.role} - {member.is_active ? 'active' : 'disabled'}</span>
          </button>
        ))}
      </div>
      {selectedUser && (
        <section className="detail-panel">
          <div className="panel-heading">
            <h3>{selectedUser.username}</h3>
            <p>User management actions</p>
          </div>
          <form className="management-form" onSubmit={updateUser}>
            <FormField error={fieldError('userEdit', 'username')}>
              <input value={userEditForm.username} onChange={(event) => updateFormField('userEdit', setUserEditForm, 'username', event.target.value)} placeholder="e.g. cashier1" required aria-invalid={Boolean(fieldError('userEdit', 'username'))} />
            </FormField>
            <FormField error={fieldError('userEdit', 'email')}>
              <input type="email" value={userEditForm.email} onChange={(event) => updateFormField('userEdit', setUserEditForm, 'email', event.target.value)} placeholder="e.g. cashier@shop.co.ke" aria-invalid={Boolean(fieldError('userEdit', 'email'))} />
            </FormField>
            <FormField error={fieldError('userEdit', 'first_name')}>
              <input value={userEditForm.first_name} onChange={(event) => updateFormField('userEdit', setUserEditForm, 'first_name', event.target.value)} placeholder="e.g. Mary" aria-invalid={Boolean(fieldError('userEdit', 'first_name'))} />
            </FormField>
            <FormField error={fieldError('userEdit', 'last_name')}>
              <input value={userEditForm.last_name} onChange={(event) => updateFormField('userEdit', setUserEditForm, 'last_name', event.target.value)} placeholder="e.g. Wanjiku" aria-invalid={Boolean(fieldError('userEdit', 'last_name'))} />
            </FormField>
            <FormField error={fieldError('userEdit', 'phone')}>
              <input value={userEditForm.phone} onChange={(event) => updateFormField('userEdit', setUserEditForm, 'phone', event.target.value)} placeholder="e.g. 254712345678" aria-invalid={Boolean(fieldError('userEdit', 'phone'))} />
            </FormField>
            <FormField error={fieldError('userEdit', 'role')}>
              <select value={userEditForm.role} onChange={(event) => updateFormField('userEdit', setUserEditForm, 'role', event.target.value)} aria-invalid={Boolean(fieldError('userEdit', 'role'))}>
                <option value="cashier">Cashier</option>
                <option value="manager">Manager</option>
                {role === 'owner' && <option value="owner">Owner</option>}
              </select>
            </FormField>
            <FormField error={fieldError('userEdit', 'is_active')}>
              <select value={userEditForm.is_active ? 'active' : 'inactive'} onChange={(event) => updateFormField('userEdit', setUserEditForm, 'is_active', event.target.value === 'active')} aria-invalid={Boolean(fieldError('userEdit', 'is_active'))}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </FormField>
            <button type="submit">Save user</button>
          </form>
          <div className="action-strip">
            <button type="button" onClick={sendPasswordReset}>Send password reset link</button>
            <button type="button" onClick={deactivateUser}>Deactivate user</button>
            <button type="button" onClick={() => setUserEditForm({ ...userEditForm, role: 'manager' })}>Promote to manager</button>
          </div>
        </section>
      )}
    </>
  );

  const renderDistributorsPanel = () => (
    <>
      <div className="panel-heading">
        <h2>Distributors</h2>
        <p>{filteredDistributors.length} of {distributors.length} suppliers</p>
      </div>
      <div className="search-stack">
        <label className="search-field">
          <Icon name="search" />
          <input
            value={distributorSearch}
            onChange={(event) => setDistributorSearch(event.target.value)}
            placeholder="Search distributors by supplier, contact, phone, or location"
          />
          <Icon name="distributors" />
        </label>
        {distributorSearch.trim() && distributorSuggestions.length > 0 && (
          <div className="suggestions-list">
            {distributorSuggestions.map((distributor) => (
              <button key={distributor.id} type="button" onClick={() => {
                setDistributorSearch(distributor.name);
                selectDistributor(distributor);
              }}>
                <strong>{distributor.name}</strong>
                <span>{distributor.contact_person || 'No contact'} - {distributor.phone || 'No phone'} - {distributor.product_count || 0} products</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <form className="management-form" onSubmit={createDistributor}>
        <FormField error={fieldError('distributor', 'name')}>
          <input value={distributorForm.name} onChange={(event) => updateFormField('distributor', setDistributorForm, 'name', event.target.value)} placeholder="e.g. Nairobi Wholesale Ltd" required aria-invalid={Boolean(fieldError('distributor', 'name'))} />
        </FormField>
        <FormField error={fieldError('distributor', 'contact_person')}>
          <input value={distributorForm.contact_person} onChange={(event) => updateFormField('distributor', setDistributorForm, 'contact_person', event.target.value)} placeholder="e.g. John Mwangi" aria-invalid={Boolean(fieldError('distributor', 'contact_person'))} />
        </FormField>
        <FormField error={fieldError('distributor', 'phone')}>
          <input value={distributorForm.phone} onChange={(event) => updateFormField('distributor', setDistributorForm, 'phone', event.target.value)} placeholder="e.g. 254712345678" aria-invalid={Boolean(fieldError('distributor', 'phone'))} />
        </FormField>
        <FormField error={fieldError('distributor', 'email')}>
          <input type="email" value={distributorForm.email} onChange={(event) => updateFormField('distributor', setDistributorForm, 'email', event.target.value)} placeholder="e.g. orders@supplier.co.ke" aria-invalid={Boolean(fieldError('distributor', 'email'))} />
        </FormField>
        <FormField error={fieldError('distributor', 'location')}>
          <input value={distributorForm.location} onChange={(event) => updateFormField('distributor', setDistributorForm, 'location', event.target.value)} placeholder="e.g. Industrial Area" aria-invalid={Boolean(fieldError('distributor', 'location'))} />
        </FormField>
        <FormField error={fieldError('distributor', 'notes')}>
          <input value={distributorForm.notes} onChange={(event) => updateFormField('distributor', setDistributorForm, 'notes', event.target.value)} placeholder="e.g. Supplies milk and bread" aria-invalid={Boolean(fieldError('distributor', 'notes'))} />
        </FormField>
        <button type="submit">Add distributor</button>
      </form>
      <div className="data-list">
        {filteredDistributors.map((distributor) => (
          <button
            key={distributor.id}
            type="button"
            className={`data-row ${String(selectedDistributorId) === String(distributor.id) ? 'selected' : ''}`}
            onClick={() => selectDistributor(distributor)}
          >
            <strong>{distributor.name}</strong>
            <span>{distributor.contact_person || 'No contact'} - {distributor.phone || 'No phone'} - {distributor.product_count || 0} products</span>
          </button>
        ))}
      </div>
      {selectedDistributor && (
        <section className="detail-panel">
          <div className="panel-heading">
            <h3>{selectedDistributor.name}</h3>
            <p>Distributor actions</p>
          </div>
          <form className="management-form" onSubmit={updateDistributor}>
            <FormField error={fieldError('distributorEdit', 'name')}>
              <input value={distributorEditForm.name} onChange={(event) => updateFormField('distributorEdit', setDistributorEditForm, 'name', event.target.value)} placeholder="e.g. Nairobi Wholesale Ltd" required aria-invalid={Boolean(fieldError('distributorEdit', 'name'))} />
            </FormField>
            <FormField error={fieldError('distributorEdit', 'contact_person')}>
              <input value={distributorEditForm.contact_person} onChange={(event) => updateFormField('distributorEdit', setDistributorEditForm, 'contact_person', event.target.value)} placeholder="e.g. John Mwangi" aria-invalid={Boolean(fieldError('distributorEdit', 'contact_person'))} />
            </FormField>
            <FormField error={fieldError('distributorEdit', 'phone')}>
              <input value={distributorEditForm.phone} onChange={(event) => updateFormField('distributorEdit', setDistributorEditForm, 'phone', event.target.value)} placeholder="e.g. 254712345678" aria-invalid={Boolean(fieldError('distributorEdit', 'phone'))} />
            </FormField>
            <FormField error={fieldError('distributorEdit', 'email')}>
              <input type="email" value={distributorEditForm.email} onChange={(event) => updateFormField('distributorEdit', setDistributorEditForm, 'email', event.target.value)} placeholder="e.g. orders@supplier.co.ke" aria-invalid={Boolean(fieldError('distributorEdit', 'email'))} />
            </FormField>
            <FormField error={fieldError('distributorEdit', 'location')}>
              <input value={distributorEditForm.location} onChange={(event) => updateFormField('distributorEdit', setDistributorEditForm, 'location', event.target.value)} placeholder="e.g. Industrial Area" aria-invalid={Boolean(fieldError('distributorEdit', 'location'))} />
            </FormField>
            <FormField error={fieldError('distributorEdit', 'notes')}>
              <input value={distributorEditForm.notes} onChange={(event) => updateFormField('distributorEdit', setDistributorEditForm, 'notes', event.target.value)} placeholder="e.g. Supplies milk and bread" aria-invalid={Boolean(fieldError('distributorEdit', 'notes'))} />
            </FormField>
            <button type="submit">Save distributor</button>
          </form>
          <div className="action-strip">
            <button type="button" onClick={removeDistributor}>Remove distributor</button>
            <button type="button" onClick={() => setActivePanel('inventory')}>Assign products in inventory</button>
          </div>
          <div className="data-list detail-list">
            {selectedDistributorProducts.length === 0 ? (
              <div>
                <strong>No linked products</strong>
                <span>Assign this distributor from the inventory product detail.</span>
              </div>
            ) : selectedDistributorProducts.map((product) => (
              <button key={product.id} type="button" className="data-row" onClick={() => {
                setActivePanel('inventory');
                selectProduct(product);
              }}>
                <strong>{product.name}</strong>
                <span>Supplies stock item - {money(product.price)} - {product.stock} available</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </>
  );

  const renderAdminPanel = () => {
    if (activePanel === 'inventory' && can('inventory')) return renderInventoryPanel();
    if (activePanel === 'users' && can('users')) return renderUsersPanel();
    if (activePanel === 'distributors' && can('distributors')) return renderDistributorsPanel();
    return renderReportsPanel();
  };

  if (!auth) {
    return (
      <div className="App auth-app">
        <main className="pos-stage auth-stage">
          {message && <div className={`toast ${message.type}`}>{message.text}</div>}
          <section className="auth-layout">
            <div className="auth-brand-panel">
              <div className="brand-lockup" aria-label="Paylof Supermarket">
                <svg className="brand-p-mark" viewBox="0 0 96 96" role="img" aria-label="Paylof P mark">
                  <path
                    d="M31 15H54C70 15 82 27 82 43C82 59 70 70 54 70H47V82H31V15Z"
                    fill="currentColor"
                  />
                  <path
                    d="M47 30H55C62 30 66 35 66 43C66 51 62 56 55 56H47V30Z"
                    fill="var(--auth-blue)"
                  />
                  <path
                    d="M21 33L31 15V82L21 63V33Z"
                    fill="currentColor"
                  />
                </svg>
                <strong>PAYLOFT</strong>
              </div>
            </div>
            <nav className="auth-icon-rail" aria-label="Login screen shortcuts">
              <button type="button" aria-label="Apps"><Icon name="inventory" /></button>
              <button type="button" aria-label="Checkout"><Icon name="checkout" /></button>
              <button type="button" aria-label="Reports"><Icon name="reports" /></button>
              <button type="button" aria-label="Sync"><Icon name="sync" /></button>
              <button type="button" aria-label="Back" className="auth-back-button">‹</button>
            </nav>
            <section className="auth-card">
              <h1>{authMode === 'login' ? 'Login' : 'Create workspace'}</h1>
              <form onSubmit={handleAuth}>
                {authMode === 'register' && (
                  <FormField error={fieldError('auth', 'business_name')}>
                    <span className="auth-input-label">Business name</span>
                    <input
                      value={authForm.business_name}
                      onChange={(event) => updateFormField('auth', setAuthForm, 'business_name', event.target.value)}
                      placeholder="e.g. Paylof Demo SME"
                      required
                      aria-invalid={Boolean(fieldError('auth', 'business_name'))}
                    />
                  </FormField>
                )}
                <FormField error={fieldError('auth', 'username') || fieldError('auth', 'non_field_errors')}>
                  <span className="auth-input-label">Username</span>
                  <input
                    value={authForm.username}
                    onChange={(event) => updateFormField('auth', setAuthForm, 'username', event.target.value)}
                    placeholder="e.g. admin"
                    required
                    aria-invalid={Boolean(fieldError('auth', 'username') || fieldError('auth', 'non_field_errors'))}
                  />
                </FormField>
                {authMode === 'register' && (
                  <FormField error={fieldError('auth', 'email')}>
                    <span className="auth-input-label">Email</span>
                    <input
                      type="email"
                      value={authForm.email}
                      onChange={(event) => updateFormField('auth', setAuthForm, 'email', event.target.value)}
                      placeholder="e.g. owner@shop.co.ke"
                      aria-invalid={Boolean(fieldError('auth', 'email'))}
                    />
                  </FormField>
                )}
                <FormField error={fieldError('auth', 'password')}>
                  <span className="auth-input-label">Password</span>
                  <input
                    type="password"
                    value={authForm.password}
                    onChange={(event) => updateFormField('auth', setAuthForm, 'password', event.target.value)}
                    placeholder={authMode === 'login' ? 'Enter your password' : 'Create a secure password'}
                    required
                    aria-invalid={Boolean(fieldError('auth', 'password'))}
                  />
                </FormField>
                <div className="auth-actions">
                  <button
                    type="button"
                    className="auth-clear"
                    onClick={() => {
                      clearFormErrors('auth');
                      setAuthForm((current) => ({
                        ...current,
                        username: '',
                        password: '',
                        ...(authMode === 'register' ? { business_name: '', email: '' } : {}),
                      }));
                    }}
                  >
                    Clear
                  </button>
                  <button type="submit" className="auth-submit">
                    {authMode === 'login' ? 'Login' : 'Create'}
                  </button>
                </div>
              </form>
              <button
                type="button"
                className="auth-switch"
                onClick={() => {
                  clearFormErrors('auth');
                  setAuthMode(authMode === 'login' ? 'register' : 'login');
                }}
              >
                {authMode === 'login' ? 'Create a new business' : 'Back to login'}
              </button>
              <p className="auth-hint">Demo: admin / admin123</p>
            </section>
          </section>
        </main>
      </div>
    );
  }

  const navItems = [
    ['inventory', 'Inventory', 'inventory', 'inventory'],
    ['checkout', 'Checkout', 'checkout', 'sales'],
    ['reports', 'Reports', 'reports', 'reports'],
    ['users', 'Users', 'users', 'users'],
    ['distributors', 'Distributors', 'distributors', 'distributors'],
    ['sync', 'Sync', 'sync', 'sales'],
  ];
  const visibleNavItems = navItems.filter(([icon, , , capability]) => {
    if (isAdmin) return !['checkout', 'sync'].includes(icon) && can(capability);
    if (icon === 'sync') return can('sales');
    return can(capability);
  });
  const activeReportLabel = (
    adminReportGroup === 'inventory'
      ? stockReportTypes.find(([value]) => value === stockReportType)?.[1]
      : adminReportGroup === 'payments'
        ? paymentReportTypes.find(([value]) => value === paymentReportType)?.[1]
        : salesReportTypes.find(([value]) => value === salesReportType)?.[1]
  ) || '';
  return (
    <div className="App">
      <main className="pos-stage">
        <span className="decor decor-cross" aria-hidden="true">x</span>
        <span className="decor decor-ring" aria-hidden="true" />
        <span className="decor decor-ring decor-ring-small" aria-hidden="true" />
        <span className="decor decor-lines" aria-hidden="true" />
        <span className="decor decor-waves" aria-hidden="true" />

        {message && <div className={`toast ${message.type}`}>{message.text}</div>}

        <section className={`pos-shell ${isAdmin ? 'admin-shell' : ''} ${isAdmin && adminMenuCollapsed ? 'menu-collapsed' : ''}`} aria-label="PAYLOFT point of sale">
          <aside className={`rail ${isAdmin ? 'admin-rail' : ''}`} aria-label="Primary navigation">
            <button
              className="rail-menu"
              title={isAdmin ? 'Toggle menu' : 'Menu'}
              aria-label={isAdmin ? 'Toggle menu' : 'Menu'}
              onClick={() => {
                if (isAdmin) setAdminMenuCollapsed((current) => !current);
              }}
            >
              <Icon name="menu" />
              {isAdmin && <span className="rail-label">Admin menu</span>}
            </button>
            {visibleNavItems.map(([icon, label, panel]) => (
              <React.Fragment key={icon}>
                <button
                  className={activePanel === panel ? 'active' : ''}
                  title={label}
                  aria-label={label}
                  onClick={() => {
                    if (icon === 'sync') syncQueuedSales();
                    else {
                      setActivePanel(panel);
                      if (isAdmin && icon === 'reports') {
                        setReportsMenuOpen((current) => activePanel === 'reports' ? !current : true);
                      } else if (isAdmin) {
                        setReportsMenuOpen(false);
                      }
                    }
                  }}
                >
                  <Icon name={icon} />
                  {isAdmin && icon === 'reports' ? (
                    <span className="rail-label report-rail-label">
                      {label}
                      <span className={`rail-chevron ${activePanel === 'reports' && reportsMenuOpen ? 'open' : ''}`} aria-hidden="true">&gt;</span>
                    </span>
                  ) : (
                    isAdmin && <span className="rail-label">{label}</span>
                  )}
                  {isAdmin && icon === 'reports' && <span className="premium-pill">Pro</span>}
                </button>
                {isAdmin && icon === 'reports' && activePanel === 'reports' && reportsMenuOpen && !adminMenuCollapsed && (
                  <div className="report-nav-tree" aria-label="Report navigation">
                    {reportGroups.map(([group, groupLabel]) => (
                      <div key={group} className="report-nav-group">
                        <button
                          type="button"
                          className={`report-group-button ${adminReportGroup === group ? 'active' : ''}`}
                          onClick={() => {
                            setActivePanel('reports');
                            setReportsMenuOpen(true);
                            setAdminReportGroup(group);
                          }}
                        >
                          <span>{groupLabel}</span>
                          <span className="premium-tag">Plus</span>
                        </button>
                        {adminReportGroup === group && group === 'sales' && (
                          <div className="report-submenu">
                            {salesReportTypes.map(([value, subLabel]) => (
                              <button
                                key={value}
                                type="button"
                                className={salesReportType === value ? 'active' : ''}
                                onClick={() => {
                                  setActivePanel('reports');
                                  setReportsMenuOpen(true);
                                  setAdminReportGroup('sales');
                                  setSalesReportType(value);
                                }}
                              >
                                {subLabel}
                              </button>
                            ))}
                          </div>
                        )}
                        {adminReportGroup === group && group === 'inventory' && (
                          <div className="report-submenu">
                            {stockReportTypes.map(([value, subLabel]) => (
                              <button
                                key={value}
                                type="button"
                                className={stockReportType === value ? 'active' : ''}
                                onClick={() => {
                                  setActivePanel('reports');
                                  setReportsMenuOpen(true);
                                  setAdminReportGroup('inventory');
                                  setStockReportType(value);
                                }}
                              >
                                {subLabel}
                              </button>
                            ))}
                          </div>
                        )}
                        {adminReportGroup === group && group === 'payments' && (
                          <div className="report-submenu">
                            {paymentReportTypes.map(([value, subLabel]) => (
                              <button
                                key={value}
                                type="button"
                                className={paymentReportType === value ? 'active' : ''}
                                onClick={() => {
                                  setActivePanel('reports');
                                  setReportsMenuOpen(true);
                                  setAdminReportGroup('payments');
                                  setPaymentReportType(value);
                                }}
                              >
                                {subLabel}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </React.Fragment>
            ))}
            <button className="rail-lock" title="Sign out" aria-label="Sign out" onClick={logout}>
              <Icon name="logout" />
              {isAdmin && <span className="rail-label">Sign out</span>}
            </button>
          </aside>

          <section className="pos-main">
            <header className="topbar">
              <div className="device-status">
                <span>{businessName}</span>
                <strong>{role.toUpperCase()}</strong>
                <span>{isOnline ? 'Online' : 'Offline'}</span>
              </div>
              <div className="brand-mark brand-wordmark">PayLoft Smart Business</div>
              <div className="cashier">
                <span>{auth.user.username}</span>
                <span className="avatar" aria-hidden="true" />
              </div>
            </header>

            {isAdmin ? (
              <section className="admin-report-panel">
                {renderAdminPanel()}
              </section>
            ) : (
            <div className="shop-grid">
              <section className="catalog-panel">
                <div className="tabs" role="tablist" aria-label="Catalog filters">
                  {tabs.map((tab) => (
                    <button
                      key={tab}
                      type="button"
                      className={activeTab === tab ? 'active' : ''}
                      onClick={() => setActiveTab(tab)}
                    >
                      {tab}
                    </button>
                  ))}
                </div>

                <div className="search-stack">
                  <label className="search-field">
                    <Icon name="search" />
                    <input
                      value={searchTerm}
                      onChange={(event) => setSearchTerm(event.target.value)}
                      placeholder="Scan barcode or search item"
                    />
                    <Icon name="barcode" />
                  </label>
                  {searchTerm.trim() && productSuggestions.length > 0 && (
                    <div className="suggestions-list">
                      {productSuggestions.map((product) => (
                        <button key={product.id} type="button" onClick={() => {
                          setSearchTerm(product.name);
                          addToCart(product);
                        }}>
                          <strong>{product.name}</strong>
                          <span>{money(product.price)} - Stock {product.stock}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div className="product-grid">
                  {loading && products.length === 0 ? (
                    <p className="quiet-state">Loading products...</p>
                  ) : filteredProducts.length === 0 ? (
                    <p className="quiet-state">No matching items</p>
                  ) : (
                    filteredProducts.slice(0, 12).map((product) => (
                      <button
                        key={product.id}
                        className="product-tile"
                        type="button"
                        onClick={() => addToCart(product)}
                        disabled={Number(product.stock) === 0 || !can('sales')}
                        aria-label={`Select ${product.name}`}
                      >
                        <ProductThumb type={product.visual} />
                        <div className="tile-line">
                          <h3>{product.name}</h3>
                          <strong>{money(product.price)}</strong>
                        </div>
                        <div className="tile-controls">
                          <span>Stock {product.stock}</span>
                          <span className={Number(product.stock) <= Number(product.low_stock_threshold || 3) ? 'low-stock-pill' : ''}>
                            {Number(product.stock) <= Number(product.low_stock_threshold || 3)
                              ? 'Low'
                              : 'Ready'}
                          </span>
                        </div>
                      </button>
                    ))
                  )}
                </div>
              </section>

              <aside className="cart-panel">
                <div className="cart-heading">
                  <div>
                    <h2>Current Sale <span>{cart.length}</span></h2>
                    <p>{can('sales') ? 'Ready for checkout' : 'Sales access unavailable'}</p>
                  </div>
                  <button type="button" className="icon-button" title="Scan item" aria-label="Scan item">
                    <Icon name="barcode" />
                  </button>
                </div>

                <div className="payment-strip" aria-label="Payment method">
                  <button
                    type="button"
                    className={paymentMethod === 'cash' ? 'active' : ''}
                    onClick={() => setPaymentMethod('cash')}
                  >
                    Cash
                  </button>
                  <button
                    type="button"
                    className={paymentMethod === 'mpesa' ? 'active' : ''}
                    onClick={() => setPaymentMethod('mpesa')}
                  >
                    M-Pesa
                  </button>
                </div>

                {paymentMethod === 'mpesa' && (
                  <FormField error={fieldError('checkout', 'customer_phone')}>
                    <input
                      className="phone-input"
                      value={customerPhone}
                      onChange={(event) => {
                        clearFieldError('checkout', 'customer_phone');
                        setCustomerPhone(event.target.value);
                      }}
                      placeholder="e.g. 254712345678"
                      aria-invalid={Boolean(fieldError('checkout', 'customer_phone'))}
                    />
                  </FormField>
                )}

                {paymentMethod === 'mpesa' && pendingMpesa && (
                  <div className={`mpesa-status ${String(pendingMpesa.status || '').toLowerCase()}`}>
                    <strong>
                      {pendingMpesa.status === 'PAID'
                        ? 'M-Pesa paid'
                        : pendingMpesa.status === 'PENDING'
                          ? 'M-Pesa pending'
                          : 'M-Pesa not completed'}
                    </strong>
                    <span>{pendingMpesa.receipt || pendingMpesa.description}</span>
                  </div>
                )}

                <div className="cart-items">
                  {cartRows.length === 0 ? (
                    <div className="empty-sale">
                      <strong>No items selected</strong>
                      <span>Scan or tap a product tile to start checkout.</span>
                    </div>
                  ) : cartRows.map((item) => (
                    <div key={item.id || item.name} className="cart-row">
                      <div>
                        <strong>{item.name}</strong>
                        <span>{item.detail}</span>
                      </div>
                      {item.live ? (
                        <div className="mini-qty">
                          <button type="button" onClick={() => decreaseItem(item.id)}>-</button>
                          <span>{item.quantity}</span>
                          <button
                            type="button"
                            onClick={() => addToCart(cart.find((row) => row.product.id === item.id).product)}
                          >
                            +
                          </button>
                        </div>
                      ) : (
                        <span className="qty">{item.quantity}</span>
                      )}
                      <strong>{money(item.price)}</strong>
                      {item.live && (
                        <button
                          type="button"
                          className="row-remove"
                          title="Remove"
                          aria-label={`Remove ${item.name}`}
                          onClick={() => removeFromCart(item.id)}
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  ))}
                </div>

                <div className="adjustments">
                  <button type="button" onClick={() => setDiscount(discount === 10 ? 0 : 10)}>
                    {discount > 0 ? 'Remove discount' : 'Apply discount'}
                  </button>
                  <button type="button" onClick={() => setCart([])}>Clear sale</button>
                </div>

                <dl className="cart-totals">
                  <div>
                    <dt>Subtotal</dt>
                    <dd>{money(visibleSubtotal)}</dd>
                  </div>
                  <div>
                    <dt>POS fee</dt>
                    <dd>{money(transactionFee)}</dd>
                  </div>
                  {discount > 0 && (
                    <div>
                      <dt>Discount</dt>
                      <dd>-{money(discount)}</dd>
                    </div>
                  )}
                </dl>

                <button
                  className="pay-button"
                  type="button"
                  onClick={createSale}
                  disabled={submitting || cart.length === 0 || !can('sales')}
                >
                  <span>
                    {submitting
                      ? 'Processing'
                      : paymentMethod === 'mpesa'
                        ? 'Send STK Push'
                        : 'Complete Sale'}
                  </span>
                  <strong>{money(totalDue)}</strong>
                </button>
              </aside>
            </div>
            )}
          </section>
        </section>

        {!isAdmin && (
          <section className="mini-status" aria-label="Business status">
            <span>{analytics?.today?.sales_count || 0} sales today</span>
            <span>{offlineQueue.length} queued</span>
            <span>{sales.length} recent</span>
            <span>{capabilities.join(', ')}</span>
          </section>
        )}

        {!isAdmin && activePanel !== 'checkout' && (
          <section className="management-panel">
            {activePanel === 'inventory' && can('inventory') && (
              <>
                <div className="panel-heading">
                  <h2>Inventory</h2>
                  <p>{products.length} products</p>
                </div>
                <form className="management-form" onSubmit={createProduct}>
                  <input value={productForm.name} onChange={(event) => setProductForm({ ...productForm, name: event.target.value })} placeholder="e.g. Bread 400g" required />
                  <input type="number" step="0.01" min="0" value={productForm.price} onChange={(event) => setProductForm({ ...productForm, price: event.target.value })} placeholder="Selling price in KES" required />
                  <input type="number" min="0" value={productForm.stock} onChange={(event) => setProductForm({ ...productForm, stock: event.target.value })} placeholder="Opening stock quantity" />
                  <input type="number" min="0" value={productForm.low_stock_threshold} onChange={(event) => setProductForm({ ...productForm, low_stock_threshold: event.target.value })} placeholder="Reorder alert level" />
                  <select value={productForm.distributor} onChange={(event) => setProductForm({ ...productForm, distributor: event.target.value })}>
                    <option value="">No distributor</option>
                    {distributors.map((distributor) => (
                      <option key={distributor.id} value={distributor.id}>{distributor.name}</option>
                    ))}
                  </select>
                  <button type="submit">Add product</button>
                </form>
                <form className="management-form stock-action-form" onSubmit={adjustStock}>
                  <select value={stockAction.product} onChange={(event) => setStockAction({ ...stockAction, product: event.target.value })} required>
                    <option value="">Select product</option>
                    {products.map((product) => (
                      <option key={product.id} value={product.id}>{product.name}</option>
                    ))}
                  </select>
                  <select value={stockAction.movement_type} onChange={(event) => setStockAction({ ...stockAction, movement_type: event.target.value })}>
                    <option value="added">Stock added</option>
                    <option value="adjusted">Manual adjustment</option>
                    <option value="damaged">Damaged stock</option>
                    <option value="lost">Lost stock</option>
                  </select>
                  <input type="number" min="1" value={stockAction.quantity} onChange={(event) => setStockAction({ ...stockAction, quantity: event.target.value })} placeholder="Units to add or remove" required />
                  <input value={stockAction.note} onChange={(event) => setStockAction({ ...stockAction, note: event.target.value })} placeholder="e.g. Restocked from supplier" />
                  <button type="submit">Update stock</button>
                </form>
                <div className="data-list">
                  {products.map((product) => (
                    <div key={product.id}>
                      <strong>{product.name}</strong>
                      <span>{money(product.price)} - Stock {product.stock} - Reorder {product.low_stock_threshold} - {product.distributor_name || 'No distributor'}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {activePanel === 'reports' && can('reports') && (
              <>
                <div className="panel-heading">
                  <h2>Reports</h2>
                  <p>Sales and stock health</p>
                </div>
                <div className="report-controls">
                  <select value={salesReportType} onChange={(event) => setSalesReportType(event.target.value)}>
                    {salesReportTypes.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                  <select value={stockReportType} onChange={(event) => setStockReportType(event.target.value)}>
                    {stockReportTypes.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                  <input type="date" value={reportDates.start_date} onChange={(event) => setReportDates({ ...reportDates, start_date: event.target.value })} />
                  <input type="date" value={reportDates.end_date} onChange={(event) => setReportDates({ ...reportDates, end_date: event.target.value })} />
                  <button type="button" onClick={fetchReports}>Refresh</button>
                </div>
                <div className="report-grid">
                  <div><span>Total sales amount</span><strong>{money(salesReport?.total_sales_amount || 0)}</strong></div>
                  <div><span>Transactions</span><strong>{salesReport?.number_of_transactions || 0}</strong></div>
                  <div><span>Average sale</span><strong>{money(salesReport?.average_transaction_value || 0)}</strong></div>
                  <div><span>Items below reorder</span><strong>{stockReport?.summary?.items_below_reorder_level || 0}</strong></div>
                </div>
                <div className="report-grid compact-report-grid">
                  <div><span>Cash sales</span><strong>{money(salesReport?.cash_vs_mpesa_sales?.cash?.total_sales_amount || 0)}</strong></div>
                  <div><span>M-Pesa sales</span><strong>{money(salesReport?.cash_vs_mpesa_sales?.mpesa?.total_sales_amount || 0)}</strong></div>
                  <div><span>Stock added</span><strong>{stockReport?.summary?.stock_added || 0}</strong></div>
                  <div><span>Stock sold</span><strong>{stockReport?.summary?.stock_sold || 0}</strong></div>
                  <div><span>Manual adjustments</span><strong>{stockReport?.summary?.stock_adjusted_manually || 0}</strong></div>
                  <div><span>Damaged/lost</span><strong>{stockReport?.summary?.damaged_or_lost_stock || 0}</strong></div>
                </div>
                <div className="report-columns">
                  <div className="data-list report-list">
                    <h3>Best-selling products</h3>
                    {(salesReport?.best_selling_products || []).map((item) => (
                      <div key={`best-${item.product__name}`}>
                        <strong>{item.product__name}</strong>
                        <span>{item.quantity_sold} sold - {money(item.revenue)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="data-list report-list">
                    <h3>Slow-selling products</h3>
                    {(salesReport?.slow_selling_products || []).map((item) => (
                      <div key={`slow-${item.product__name}`}>
                        <strong>{item.product__name}</strong>
                        <span>{item.quantity_sold} sold - {money(item.revenue)}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="data-list stock-report-list">
                  <h3>Selected sales report</h3>
                  {(salesReport?.breakdown || []).map((item, index) => {
                    const label = item.product__name || item.payment_method || item.user__username || item.period || `Row ${index + 1}`;
                    const detail = item.quantity_sold
                      ? `${item.quantity_sold} sold - ${money(item.total_sales_amount)}`
                      : `${item.number_of_transactions || 0} transactions - ${money(item.total_sales_amount)}`;
                    return (
                      <div key={`${label}-${index}`}>
                        <strong>{label}</strong>
                        <span>{detail}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="data-list stock-report-list">
                  {(stockReport?.products || []).map((item) => (
                    <div key={item.product_name}>
                      <strong>{item.product_name}</strong>
                      <span>Available {item.quantity_available} - Reorder {item.reorder_level} - Added {item.stock_added} - Sold {item.stock_sold} - Adjusted {item.stock_adjusted_manually}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {activePanel === 'users' && can('users') && (
              <>
                <div className="panel-heading">
                  <h2>Users</h2>
                  <p>{team.length} members</p>
                </div>
                <form className="management-form" onSubmit={createUser}>
                  <input value={userForm.username} onChange={(event) => setUserForm({ ...userForm, username: event.target.value })} placeholder="e.g. cashier1" required />
                  <input value={userForm.email} onChange={(event) => setUserForm({ ...userForm, email: event.target.value })} placeholder="e.g. cashier@shop.co.ke" />
                  <input type="password" value={userForm.password} onChange={(event) => setUserForm({ ...userForm, password: event.target.value })} placeholder="Temporary password" required />
                  <select value={userForm.role} onChange={(event) => setUserForm({ ...userForm, role: event.target.value })}>
                    <option value="cashier">Cashier</option>
                    <option value="manager">Manager</option>
                    {role === 'owner' && <option value="owner">Owner</option>}
                  </select>
                  <button type="submit">Add user</button>
                </form>
                <div className="data-list">
                  {team.map((member) => (
                    <div key={member.id}>
                      <strong>{member.username}</strong>
                      <span>{member.role} - {member.is_active ? 'active' : 'disabled'}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {activePanel === 'distributors' && can('distributors') && (
              <>
                <div className="panel-heading">
                  <h2>Distributors</h2>
                  <p>{distributors.length} suppliers</p>
                </div>
                <form className="management-form" onSubmit={createDistributor}>
                  <input value={distributorForm.name} onChange={(event) => setDistributorForm({ ...distributorForm, name: event.target.value })} placeholder="e.g. Nairobi Wholesale Ltd" required />
                  <input value={distributorForm.contact_person} onChange={(event) => setDistributorForm({ ...distributorForm, contact_person: event.target.value })} placeholder="e.g. John Mwangi" />
                  <input value={distributorForm.phone} onChange={(event) => setDistributorForm({ ...distributorForm, phone: event.target.value })} placeholder="e.g. 254712345678" />
                  <input value={distributorForm.location} onChange={(event) => setDistributorForm({ ...distributorForm, location: event.target.value })} placeholder="e.g. Industrial Area" />
                  <button type="submit">Add distributor</button>
                </form>
                <div className="data-list">
                  {distributors.map((distributor) => (
                    <div key={distributor.id}>
                      <strong>{distributor.name}</strong>
                      <span>{distributor.contact_person || 'No contact'} - {distributor.phone || 'No phone'} - {distributor.product_count || 0} products</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
