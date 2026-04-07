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
            const { title, message, actions = [] } = options;
            titleNode.textContent = title || 'Notice';
            messageNode.textContent = message || '';
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

    function setSidebarLinks(userId) {
        const dashboardLink = document.getElementById('account-sidebar-dashboard-link');
        const transactionLink = document.getElementById('account-sidebar-transaction-link');
        const assetLink = document.getElementById('account-sidebar-asset-link');
        const sidebar = document.getElementById('account-sidebar-links');

        if (sidebar) {
            sidebar.hidden = false;
        }

        if (dashboardLink) {
            dashboardLink.href = `/users/${userId}`;
        }

        if (transactionLink) {
            transactionLink.href = `/users/${userId}/transactions`;
        }

        if (assetLink) {
            assetLink.href = `/users/${userId}/assets`;
        }
    }

    function updateProfilePreview(user) {
        const username = String(user.username || '').trim();
        const email = String(user.email || '').trim();
        const imagePath = String(user.image_path || '').trim();

        const displayUsername = document.getElementById('account-display-username');
        const displayEmail = document.getElementById('account-display-email');
        const fallback = document.getElementById('account-avatar-fallback');
        const initial = document.getElementById('account-avatar-initial');
        const image = document.getElementById('account-avatar-image');

        if (displayUsername) {
            displayUsername.textContent = username || 'User';
        }

        if (displayEmail) {
            displayEmail.textContent = email;
        }

        if (initial) {
            initial.textContent = username ? username.charAt(0).toUpperCase() : 'U';
        }

        if (image && fallback) {
            if (imagePath) {
                image.src = `/${imagePath.replace(/^\/+/, '')}`;
                image.hidden = false;
                fallback.hidden = true;
            } else {
                image.hidden = true;
                fallback.hidden = false;
            }
        }
    }

    function fillForm(user) {
        const usernameInput = document.getElementById('account-username');
        const emailInput = document.getElementById('account-email');
        const imageFileName = document.getElementById('account-image-file-name');
        const existingFileName = user.image_file_name || (user.image_path ? String(user.image_path).split('/').pop() : '');

        if (usernameInput) {
            usernameInput.value = user.username || '';
        }

        if (emailInput) {
            emailInput.value = user.email || '';
        }

        if (imageFileName) {
            imageFileName.textContent = existingFileName
                ? `Current file: ${existingFileName}. Upload coming soon.`
                : 'Upload coming soon. Current profile image is shown above.';
        }
    }

    async function initializeAccountPage() {
        const accountForm = document.getElementById('account-form');
        if (!accountForm) {
            return;
        }

        const modal = createModalController();
        const auth = await window.requireAuth('/login');
        if (!auth) {
            return;
        }

        let { user, token } = auth;
        setSidebarLinks(user.id);
        fillForm(user);
        updateProfilePreview(user);

        accountForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            if (!accountForm.checkValidity()) {
                accountForm.reportValidity();
                return;
            }

            const usernameValue = String(document.getElementById('account-username')?.value || '').trim();
            const emailValue = String(document.getElementById('account-email')?.value || '').trim();

            if (!usernameValue || !emailValue) {
                modal.info('Username and email are required.', 'Validation error');
                return;
            }

            const payload = {
                user_id: user.id,
                username: usernameValue,
                email: emailValue,
                phone_no: user.phone_no || null,
                image_file_name: user.image_path ? String(user.image_path).split('/').pop() : null,
            };

            const response = await fetch('/api/users/', {
                method: 'PATCH',
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });

            if (response.status === 401) {
                window.location.assign('/login');
                return;
            }

            const body = await response.json().catch(() => ({}));
            if (!response.ok) {
                modal.info(window.parseApiError(body, 'Unable to update account details.'), 'Error');
                return;
            }

            window.invalidateCurrentUserCache();
            const refreshedUser = await window.get_current_user({ forceRefresh: true });
            if (refreshedUser) {
                user = refreshedUser;
                token = window.getStoredToken() || token;
            }

            fillForm(user);
            updateProfilePreview(user);
            await window.updateAuthUI();
            modal.info('Account details updated successfully.', 'Success');
        });

        const logoutButton = document.getElementById('account-logout-button');
        if (logoutButton) {
            logoutButton.addEventListener('click', async () => {
                await window.logout();
            });
        }

        const deleteButton = document.getElementById('delete-account-button');
        if (deleteButton) {
            deleteButton.addEventListener('click', () => {
                modal.openModal({
                    title: 'Delete Account',
                    message: 'Are you sure you want to permanently delete your account?',
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
                                const response = await fetch(`/api/users/?user_id=${user.id}`, {
                                    method: 'DELETE',
                                    headers: {
                                        Authorization: `Bearer ${token}`,
                                    },
                                });

                                if (response.status === 401) {
                                    window.location.assign('/login');
                                    return;
                                }

                                if (!response.ok) {
                                    const payload = await response.json().catch(() => ({}));
                                    modal.info(window.parseApiError(payload, 'Unable to delete account.'), 'Error');
                                    return;
                                }

                                modal.closeModal();
                                window.logout();
                            },
                        },
                    ],
                });
            });
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        initializeAccountPage();
    });
}());
