const AUTH_TOKEN_KEY = 'access_token';

let cachedUser = null;
let cachedToken = null;
let inFlightUserRequest = null;
let inFlightToken = null;

function getStoredToken() {
	return localStorage.getItem(AUTH_TOKEN_KEY);
}

function get_stored_token() {
	return getStoredToken();
}

function setCachedUser(token, user) {
	cachedToken = token;
	cachedUser = user;
}

function clearAuthCache() {
	cachedToken = null;
	cachedUser = null;
	inFlightUserRequest = null;
	inFlightToken = null;
}

function clearStoredToken() {
	localStorage.removeItem(AUTH_TOKEN_KEY);
}

function invalidateCurrentUserCache() {
	clearAuthCache();
}

function invalidate_current_user_cache() {
	invalidateCurrentUserCache();
}

function parseApiError(payload, fallbackMessage) {
	if (payload == null) {
		return fallbackMessage;
	}

	if (typeof payload === 'string') {
		return payload;
	}

	if (Array.isArray(payload)) {
		return payload.map((part) => parseApiError(part, '')).filter(Boolean).join(', ') || fallbackMessage;
	}

	if (typeof payload === 'object') {
		if ('detail' in payload) {
			return parseApiError(payload.detail, fallbackMessage);
		}

		if ('message' in payload) {
			return parseApiError(payload.message, fallbackMessage);
		}
	}

	return fallbackMessage;
}

async function requireAuth(redirectPath = '/login') {
	const token = getStoredToken();

	if (!token) {
		window.location.assign(redirectPath);
		return null;
	}

	const user = await get_current_user();
	if (!user) {
		window.location.assign(redirectPath);
		return null;
	}

	return { token, user };
}

async function get_current_user(options = {}) {
	const { forceRefresh = false } = options;
	const token = getStoredToken();

	if (!token) {
		clearAuthCache();
		return null;
	}

	if (!forceRefresh && cachedToken === token && cachedUser) {
		return cachedUser;
	}

	if (!forceRefresh && inFlightUserRequest && inFlightToken === token) {
		return inFlightUserRequest;
	}

	cachedToken = token;
	inFlightToken = token;
	inFlightUserRequest = fetch('/api/users/me', {
		headers: {
			Authorization: `Bearer ${token}`,
		},
	})
		.then(async (response) => {
			if (!response.ok) {
				if (response.status === 401 || response.status === 403) {
					clearStoredToken();
				}
				clearAuthCache();
				return null;
			}

			const user = await response.json();
			setCachedUser(token, user);
			inFlightToken = null;
			return user;
		})
		.catch(() => {
			clearAuthCache();
			return null;
		});

	return inFlightUserRequest;
}

async function updateAuthUI() {
	const loggedInNav = document.getElementById('navbar-logged-in');
	const loggedOutNav = document.getElementById('navbar-logged-out');
	const brandLink = document.getElementById('navbar-brand-link');
	const accountLink = document.getElementById('navbar-account-link');
	const dashboardSidebar = document.getElementById('dashboard-sidebar-auth');
	const homeSidebar = document.getElementById('home-sidebar-links');
	const transactionsSidebar = document.getElementById('transactions-sidebar-links');
	const assetsSidebar = document.getElementById('assets-sidebar-links');
	const accountSidebar = document.getElementById('account-sidebar-links');
	const homeUserWelcome = document.getElementById('home-user-welcome');
	const homeSidebarHomeLink = document.getElementById('home-sidebar-home-link');
	const homeSidebarDashboardLink = document.getElementById('home-sidebar-dashboard-link');
	const homeSidebarTransactionLink = document.getElementById('home-sidebar-transaction-link');
	const homeSidebarAssetLink = document.getElementById('home-sidebar-asset-link');
	const homeSidebarAccountLink = document.getElementById('home-sidebar-account-link');
	const transactionsSidebarDashboardLink = document.getElementById('transactions-sidebar-dashboard-link');
	const transactionsSidebarTransactionLink = document.getElementById('transactions-sidebar-transaction-link');
	const transactionsSidebarAssetLink = document.getElementById('transactions-sidebar-asset-link');
	const transactionsSidebarAccountLink = document.getElementById('transactions-sidebar-account-link');
	const assetsSidebarDashboardLink = document.getElementById('assets-sidebar-dashboard-link');
	const assetsSidebarTransactionLink = document.getElementById('assets-sidebar-transaction-link');
	const assetsSidebarAssetLink = document.getElementById('assets-sidebar-asset-link');
	const assetsSidebarAccountLink = document.getElementById('assets-sidebar-account-link');
	const accountSidebarDashboardLink = document.getElementById('account-sidebar-dashboard-link');
	const accountSidebarTransactionLink = document.getElementById('account-sidebar-transaction-link');
	const accountSidebarAssetLink = document.getElementById('account-sidebar-asset-link');

	const user = await get_current_user();
	const isLoggedIn = Boolean(user);

	if (loggedInNav) {
		loggedInNav.hidden = !isLoggedIn;
	}

	if (loggedOutNav) {
		loggedOutNav.hidden = isLoggedIn;
	}

	if (brandLink) {
		brandLink.href = isLoggedIn ? `/users/${user.id}` : '/';
	}

	if (accountLink) {
		accountLink.textContent = isLoggedIn ? user.username : 'Account';
		accountLink.href = isLoggedIn ? '/account' : '/login';
	}

	if (dashboardSidebar) {
		dashboardSidebar.hidden = !isLoggedIn;
	}

	if (homeSidebar) {
		homeSidebar.hidden = !isLoggedIn;
	}

	if (transactionsSidebar) {
		transactionsSidebar.hidden = !isLoggedIn;
	}

	if (assetsSidebar) {
		assetsSidebar.hidden = !isLoggedIn;
	}

	if (accountSidebar) {
		accountSidebar.hidden = !isLoggedIn;
	}

	if (homeUserWelcome) {
		homeUserWelcome.hidden = !isLoggedIn;
		homeUserWelcome.textContent = isLoggedIn ? `Welcome back, ${user.username}.` : '';
	}

	if (homeSidebarHomeLink) {
		homeSidebarHomeLink.href = '/';
	}

	if (homeSidebarDashboardLink) {
		homeSidebarDashboardLink.href = isLoggedIn ? `/users/${user.id}` : '#';
	}

	if (homeSidebarTransactionLink) {
		homeSidebarTransactionLink.href = isLoggedIn ? `/users/${user.id}/transactions` : '#';
	}

	if (homeSidebarAssetLink) {
		homeSidebarAssetLink.href = isLoggedIn ? `/users/${user.id}/assets` : '#';
	}

	if (homeSidebarAccountLink) {
		homeSidebarAccountLink.href = isLoggedIn ? '/account' : '#';
	}

	if (transactionsSidebarDashboardLink) {
		transactionsSidebarDashboardLink.href = isLoggedIn ? `/users/${user.id}` : '#';
	}

	if (transactionsSidebarTransactionLink) {
		transactionsSidebarTransactionLink.href = isLoggedIn ? `/users/${user.id}/transactions` : '#';
	}

	if (transactionsSidebarAssetLink) {
		transactionsSidebarAssetLink.href = isLoggedIn ? `/users/${user.id}/assets` : '#';
	}

	if (transactionsSidebarAccountLink) {
		transactionsSidebarAccountLink.href = isLoggedIn ? '/account' : '#';
	}

	if (assetsSidebarDashboardLink) {
		assetsSidebarDashboardLink.href = isLoggedIn ? `/users/${user.id}` : '#';
	}

	if (assetsSidebarTransactionLink) {
		assetsSidebarTransactionLink.href = isLoggedIn ? `/users/${user.id}/transactions` : '#';
	}

	if (assetsSidebarAssetLink) {
		assetsSidebarAssetLink.href = isLoggedIn ? `/users/${user.id}/assets` : '#';
	}

	if (assetsSidebarAccountLink) {
		assetsSidebarAccountLink.href = isLoggedIn ? '/account' : '#';
	}

	if (accountSidebarDashboardLink) {
		accountSidebarDashboardLink.href = isLoggedIn ? `/users/${user.id}` : '#';
	}

	if (accountSidebarTransactionLink) {
		accountSidebarTransactionLink.href = isLoggedIn ? `/users/${user.id}/transactions` : '#';
	}

	if (accountSidebarAssetLink) {
		accountSidebarAssetLink.href = isLoggedIn ? `/users/${user.id}/assets` : '#';
	}

	return user;
}

async function logout() {
	clearStoredToken();
	clearAuthCache();
	window.location.assign('/');
}

window.get_current_user = get_current_user;
window.getCurrentUser = get_current_user;
window.getStoredToken = getStoredToken;
window.get_stored_token = get_stored_token;
window.invalidateCurrentUserCache = invalidateCurrentUserCache;
window.invalidate_current_user_cache = invalidate_current_user_cache;
window.parseApiError = parseApiError;
window.requireAuth = requireAuth;
window.logout = logout;
window.updateAuthUI = updateAuthUI;

document.addEventListener('DOMContentLoaded', () => {
	updateAuthUI();
});
