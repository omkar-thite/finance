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

    async function initTransactionsPage(modal, auth) {
        const form = document.getElementById('create-transaction-form');
        const rows = document.querySelectorAll('tr[data-transaction-id]');
        const { token, user } = auth;

        rows.forEach((row) => {
            const ownerId = Number(row.getAttribute('data-transaction-user-id'));
            const actions = row.querySelector('.row-actions');
            if (actions) {
                actions.hidden = ownerId !== user.id;
            }
        });

        if (form) {
            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                const body = {
                    type: form.type.value,
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
                window.location.reload();
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
                window.location.reload();
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
                                window.location.reload();
                            },
                        },
                    ],
                });
            }
        });
    }

    async function initAssetsPage(modal, auth) {
        const form = document.getElementById('create-asset-form');
        const { token, user } = auth;

        const rows = document.querySelectorAll('tr[data-asset-id]');
        rows.forEach((row) => {
            const ownerId = Number(row.getAttribute('data-asset-user-id'));
            const actions = row.querySelector('.row-actions');
            if (actions) {
                actions.hidden = ownerId !== user.id;
            }
        });

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
                window.location.reload();
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
                window.location.reload();
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
