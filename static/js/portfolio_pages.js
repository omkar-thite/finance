(function () {
    function createModalController() {
        const modal = document.getElementById('app-modal');
        const titleNode = document.getElementById('app-modal-title');
        const messageNode = document.getElementById('app-modal-message');
        const actionsNode = document.getElementById('app-modal-actions');

        if (!modal || !titleNode || !messageNode || !actionsNode) {
            return null;
        }

        function closeModal() {
            modal.hidden = true;
            actionsNode.innerHTML = '';
        }

        function openModal(options) {
            const { title, message, actions = [], htmlContent = '' } = options;
            titleNode.textContent = title || 'Notice';
            messageNode.textContent = message || '';
            if (htmlContent) {
                messageNode.innerHTML = htmlContent;
            }
            actionsNode.innerHTML = '';

            actions.forEach((action) => {
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = action.label;
                button.className = action.className || 'btn-auth';
                button.addEventListener('click', async () => {
                    if (action.onClick) {
                        await action.onClick();
                    }
                });
                actionsNode.appendChild(button);
            });

            modal.hidden = false;
        }

        modal.addEventListener('click', (event) => {
            if (event.target instanceof HTMLElement && event.target.hasAttribute('data-modal-close')) {
                closeModal();
            }
        });

        return {
            closeModal,
            openModal,
            info(message, title = 'Notice') {
                openModal({
                    title,
                    message,
                    actions: [{ label: 'Close', className: 'btn-auth', onClick: closeModal }],
                });
            },
        };
    }

    function requestNumber(modal, options) {
        const { title, label, defaultValue } = options;

        return new Promise((resolve) => {
            modal.openModal({
                title,
                message: '',
                htmlContent: `
                    <label class="modal-input-wrap">
                        <span>${label}</span>
                        <input id="app-modal-number-input" type="number" min="0" step="1" value="${defaultValue}">
                    </label>
                `,
                actions: [
                    {
                        label: 'Cancel',
                        className: 'btn-auth btn-neutral',
                        onClick: () => {
                            modal.closeModal();
                            resolve(null);
                        },
                    },
                    {
                        label: 'Save',
                        className: 'btn-auth',
                        onClick: () => {
                            const input = document.getElementById('app-modal-number-input');
                            const value = input ? Number(input.value) : NaN;
                            modal.closeModal();
                            resolve(Number.isFinite(value) ? value : null);
                        },
                    },
                ],
            });
        });
    }

    function authHeader(token) {
        return {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
        };
    }

    async function safeJson(response) {
        return response.json().catch(() => ({}));
    }

    function makeEmptyRow(colSpan, message) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = colSpan;
        cell.style.textAlign = 'center';
        cell.style.color = 'var(--muted)';
        cell.textContent = message;
        row.appendChild(cell);
        return row;
    }

    function toFixedNumber(value, digits = 2) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) {
            return (0).toFixed(digits);
        }
        return parsed.toFixed(digits);
    }

    function createTransactionRows(transaction, userId) {
        const fragment = document.createDocumentFragment();

        const row = document.createElement('tr');
        row.setAttribute('data-transaction-id', String(transaction.id));
        row.setAttribute('data-transaction-user-id', String(transaction.user_id));

        const typeCell = document.createElement('td');
        const badge = document.createElement('span');
        const rawType = transaction.type_ ?? transaction.type;
        const typeValue = String(rawType || '').toLowerCase();
        badge.className = `badge ${typeValue === 'buy' ? 'badge-buy' : 'badge-sell'}`;
        badge.textContent = typeValue ? `${typeValue.charAt(0).toUpperCase()}${typeValue.slice(1)}` : '-';
        typeCell.appendChild(badge);

        const dateCell = document.createElement('td');
        dateCell.textContent = transaction.date_created || transaction.date || '-';

        const nameCell = document.createElement('td');
        nameCell.textContent = transaction.instrument || '-';

        const unitsCell = document.createElement('td');
        unitsCell.textContent = String(transaction.units ?? '-');

        const rateCell = document.createElement('td');
        rateCell.textContent = toFixedNumber(transaction.rate);

        const netAmountCell = document.createElement('td');
        const netAmount = Number(transaction.units || 0) * Number(transaction.rate || 0);
        netAmountCell.textContent = toFixedNumber(netAmount);

        const actionsCell = document.createElement('td');
        actionsCell.className = 'row-actions';
        actionsCell.hidden = Number(transaction.user_id) !== Number(userId);
        actionsCell.innerHTML = [
            '<button class="btn-warning edit-transaction-btn" title="Edit" type="button">&#9998;</button>',
            '<button class="btn-danger delete-transaction-btn" title="Delete" type="button">&#10005;</button>',
        ].join('');

        row.append(typeCell, dateCell, nameCell, unitsCell, rateCell, netAmountCell, actionsCell);
        fragment.appendChild(row);

        const charges = Number(transaction.charges || 0);
        if (charges > 0) {
            const chargesRow = document.createElement('tr');
            chargesRow.className = 'charges-row';
            chargesRow.innerHTML = [
                '<td></td>',
                '<td></td>',
                '<td>&#8627; Charges</td>',
                '<td></td>',
                '<td></td>',
                `<td>${toFixedNumber(charges)}</td>`,
                '<td></td>',
            ].join('');
            fragment.appendChild(chargesRow);
        }

        return fragment;
    }

    function createAssetRow(asset, userId) {
        const row = document.createElement('tr');
        row.setAttribute('data-asset-id', String(asset.instrument_id));
        row.setAttribute('data-asset-user-id', String(userId));

        const instrumentCell = document.createElement('td');
        instrumentCell.textContent = String(asset.instrument ?? '-');

        const quantityCell = document.createElement('td');
        quantityCell.textContent = String(asset.quantity ?? '-');

        const averageRateCell = document.createElement('td');
        averageRateCell.textContent = toFixedNumber(asset.average_rate);

        const investedCell = document.createElement('td');
        const investedAmount = Number(asset.quantity || 0) * Number(asset.average_rate || 0);
        investedCell.textContent = toFixedNumber(investedAmount);

        const actionsCell = document.createElement('td');
        actionsCell.className = 'row-actions';
        actionsCell.hidden = false;
        actionsCell.innerHTML = [
            '<button class="btn-warning edit-asset-btn" type="button" title="Edit">&#9998;</button>',
            '<button class="btn-danger delete-asset-btn" type="button" title="Delete">&#10005;</button>',
        ].join('');

        row.append(instrumentCell, quantityCell, averageRateCell, investedCell, actionsCell);
        return row;
    }

    async function initTransactionsPage(modal, auth) {
        const form = document.getElementById('create-transaction-form');
        const tbody = document.getElementById('transactions-table-body');
        const loadMoreButton = document.getElementById('transactions-load-more-btn');
        const { token, user } = auth;
        const pageLimit = 10;
        let skip = 0;
        let hasMore = false;
        let isLoading = false;

        async function loadTransactionsPage(options = {}) {
            const { reset = false } = options;

            if (!tbody || isLoading) {
                return;
            }

            if (reset) {
                skip = 0;
                hasMore = true;
                tbody.innerHTML = '';
            }

            isLoading = true;
            if (loadMoreButton) {
                loadMoreButton.disabled = true;
                loadMoreButton.textContent = 'Loading...';
            }

            try {
                const response = await fetch(`/api/users/${user.id}/transactions?skip=${skip}&limit=${pageLimit}`, {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                });

                if (response.status === 401) {
                    window.location.assign('/login');
                    return;
                }

                const payload = await safeJson(response);
                if (!response.ok) {
                    modal.info(window.parseApiError(payload, 'Unable to fetch transactions.'), 'Error');
                    if (loadMoreButton) {
                        loadMoreButton.hidden = true;
                    }
                    return;
                }

                const transactions = Array.isArray(payload.transactions) ? payload.transactions : [];
                if (reset && transactions.length === 0) {
                    tbody.appendChild(makeEmptyRow(7, 'No transactions found.'));
                } else {
                    transactions.forEach((transaction) => {
                        tbody.appendChild(createTransactionRows(transaction, user.id));
                    });
                }

                skip += transactions.length;
                hasMore = Boolean(payload.has_more);

                if (loadMoreButton) {
                    loadMoreButton.hidden = !hasMore;
                }
            } finally {
                isLoading = false;
                if (loadMoreButton) {
                    loadMoreButton.disabled = false;
                    loadMoreButton.textContent = 'Load more';
                }
            }
        }

        if (loadMoreButton) {
            loadMoreButton.addEventListener('click', async () => {
                if (!hasMore) {
                    loadMoreButton.hidden = true;
                    return;
                }
                await loadTransactionsPage();
            });
        }

        await loadTransactionsPage({ reset: true });

        if (form) {
            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                const body = {
                    type_: form.type.value,
                    instrument_id: Number(form.instrument_id.value),
                    units: Number(form.units.value),
                    rate: Number(form.rate.value),
                    charges: Number(form.charges.value || 0),
                    user_id: user.id,
                };

                const response = await fetch('/api/transactions/', {
                    method: 'POST',
                    headers: authHeader(token),
                    body: JSON.stringify(body),
                });

                if (response.status === 401) {
                    window.location.assign('/login');
                    return;
                }

                const payload = await safeJson(response);
                if (!response.ok) {
                    modal.info(window.parseApiError(payload, 'Unable to create transaction.'), 'Error');
                    return;
                }

                modal.info('Transaction created successfully.', 'Success');
                form.reset();
                await loadTransactionsPage({ reset: true });
            });
        }

        document.addEventListener('click', async (event) => {
            const target = event.target instanceof HTMLElement ? event.target : null;
            if (!target) {
                return;
            }

            const editButton = target.closest('.edit-transaction-btn');
            if (editButton) {
                const row = editButton.closest('tr[data-transaction-id]');
                if (!row) {
                    return;
                }

                const transactionId = Number(row.getAttribute('data-transaction-id'));
                const unitsValue = await requestNumber(modal, {
                    title: 'Edit Transaction',
                    label: 'Updated units',
                    defaultValue: 1,
                });
                if (unitsValue === null) {
                    return;
                }

                const updateResponse = await fetch('/api/transactions/', {
                    method: 'PATCH',
                    headers: authHeader(token),
                    body: JSON.stringify({
                        id: transactionId,
                        user_id: user.id,
                        units: Number(unitsValue),
                    }),
                });

                if (updateResponse.status === 401) {
                    window.location.assign('/login');
                    return;
                }

                const updatePayload = await safeJson(updateResponse);
                if (updateResponse.status === 403) {
                    modal.info('You do not have permission to edit this item.', 'Permission denied');
                    return;
                }

                if (!updateResponse.ok) {
                    modal.info(window.parseApiError(updatePayload, 'Unable to update transaction.'), 'Error');
                    return;
                }

                modal.info('Transaction updated successfully.', 'Success');
                await loadTransactionsPage({ reset: true });
                return;
            }

            const deleteButton = target.closest('.delete-transaction-btn');
            if (deleteButton) {
                const row = deleteButton.closest('tr[data-transaction-id]');
                if (!row) {
                    return;
                }

                const transactionId = Number(row.getAttribute('data-transaction-id'));
                modal.openModal({
                    title: 'Delete Transaction',
                    message: 'Are you sure you want to delete this transaction?',
                    actions: [
                        {
                            label: 'Cancel',
                            className: 'btn-auth btn-neutral',
                            onClick: () => modal.closeModal(),
                        },
                        {
                            label: 'Confirm Delete',
                            className: 'btn-danger',
                            onClick: async () => {
                                const deleteResponse = await fetch(`/api/transactions/?user_id=${user.id}&trx_id=${transactionId}`, {
                                    method: 'DELETE',
                                    headers: {
                                        Authorization: `Bearer ${token}`,
                                    },
                                });

                                if (deleteResponse.status === 401) {
                                    window.location.assign('/login');
                                    return;
                                }

                                if (deleteResponse.status === 403) {
                                    modal.info('You do not have permission to delete this item.', 'Permission denied');
                                    return;
                                }

                                if (!deleteResponse.ok) {
                                    const deletePayload = await safeJson(deleteResponse);
                                    modal.info(window.parseApiError(deletePayload, 'Unable to delete transaction.'), 'Error');
                                    return;
                                }

                                modal.closeModal();
                                modal.info('Transaction deleted successfully.', 'Success');
                                await loadTransactionsPage({ reset: true });
                            },
                        },
                    ],
                });
            }
        });
    }

    async function initAssetsPage(modal, auth) {
        const form = document.getElementById('create-asset-form');
        const tbody = document.getElementById('assets-table-body');
        const loadMoreButton = document.getElementById('assets-load-more-btn');
        const { token, user } = auth;
        const pageLimit = 10;
        let skip = 0;
        let hasMore = false;
        let isLoading = false;

        async function loadAssetsPage(options = {}) {
            const { reset = false } = options;

            if (!tbody || isLoading) {
                return;
            }

            if (reset) {
                skip = 0;
                hasMore = true;
                tbody.innerHTML = '';
            }

            isLoading = true;
            if (loadMoreButton) {
                loadMoreButton.disabled = true;
                loadMoreButton.textContent = 'Loading...';
            }

            try {
                const response = await fetch(`/api/users/${user.id}/holdings?skip=${skip}&limit=${pageLimit}`, {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                });

                if (response.status === 401) {
                    window.location.assign('/login');
                    return;
                }

                const payload = await safeJson(response);
                if (!response.ok) {
                    modal.info(window.parseApiError(payload, 'Unable to fetch assets.'), 'Error');
                    if (loadMoreButton) {
                        loadMoreButton.hidden = true;
                    }
                    return;
                }

                const holdings = Array.isArray(payload.holdings) ? payload.holdings : [];
                if (reset && holdings.length === 0) {
                    tbody.appendChild(makeEmptyRow(5, 'No assets found.'));
                } else {
                    holdings.forEach((asset) => {
                        tbody.appendChild(createAssetRow(asset, user.id));
                    });
                }

                skip += holdings.length;
                hasMore = Boolean(payload.has_more);

                if (loadMoreButton) {
                    loadMoreButton.hidden = !hasMore;
                }
            } finally {
                isLoading = false;
                if (loadMoreButton) {
                    loadMoreButton.disabled = false;
                    loadMoreButton.textContent = 'Load more';
                }
            }
        }

        if (loadMoreButton) {
            loadMoreButton.addEventListener('click', async () => {
                if (!hasMore) {
                    loadMoreButton.hidden = true;
                    return;
                }
                await loadAssetsPage();
            });
        }

        await loadAssetsPage({ reset: true });

        if (form) {
            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                const body = {
                    instrument_id: Number(form.instrument_id.value),
                    quantity: Number(form.quantity.value),
                    average_rate: Number(form.average_rate.value),
                    user_id: user.id,
                };

                const response = await fetch(`/api/users/${user.id}/holdings`, {
                    method: 'POST',
                    headers: authHeader(token),
                    body: JSON.stringify(body),
                });

                if (response.status === 401) {
                    window.location.assign('/login');
                    return;
                }

                const payload = await safeJson(response);
                if (!response.ok) {
                    modal.info(window.parseApiError(payload, 'Unable to create asset.'), 'Error');
                    return;
                }

                modal.info('Asset created successfully.', 'Success');
                form.reset();
                await loadAssetsPage({ reset: true });
            });
        }

        document.addEventListener('click', async (event) => {
            const target = event.target instanceof HTMLElement ? event.target : null;
            if (!target) {
                return;
            }

            const editButton = target.closest('.edit-asset-btn');
            if (editButton) {
                const row = editButton.closest('tr[data-asset-id]');
                if (!row) {
                    return;
                }

                const assetId = Number(row.getAttribute('data-asset-id'));
                const quantityValue = await requestNumber(modal, {
                    title: 'Edit Asset',
                    label: 'Updated quantity',
                    defaultValue: 1,
                });
                if (quantityValue === null) {
                    return;
                }

                const updateResponse = await fetch(`/api/users/${user.id}/holdings/${assetId}`, {
                    method: 'PATCH',
                    headers: authHeader(token),
                    body: JSON.stringify({ total_units: Number(quantityValue) }),
                });

                if (updateResponse.status === 401) {
                    window.location.assign('/login');
                    return;
                }

                if (updateResponse.status === 403) {
                    modal.info('You do not have permission to edit this asset.', 'Permission denied');
                    return;
                }

                const payload = await safeJson(updateResponse);
                if (!updateResponse.ok) {
                    modal.info(window.parseApiError(payload, 'Unable to update asset.'), 'Error');
                    return;
                }

                modal.info('Asset updated successfully.', 'Success');
                await loadAssetsPage({ reset: true });
                return;
            }

            const deleteButton = target.closest('.delete-asset-btn');
            if (deleteButton) {
                modal.info('Asset delete API is not available yet.', 'Coming soon');
            }
        });
    }

    async function initializePage() {
        const isTransactionsPage = Boolean(document.getElementById('create-transaction-form'));
        const isAssetsPage = Boolean(document.getElementById('create-asset-form'));

        if (!isTransactionsPage && !isAssetsPage) {
            return;
        }

        const modal = createModalController();
        const auth = await window.requireAuth('/login');
        if (!auth) {
            return;
        }

        if (isTransactionsPage) {
            await initTransactionsPage(modal, auth);
        }

        if (isAssetsPage) {
            await initAssetsPage(modal, auth);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        initializePage();
    });
}());
