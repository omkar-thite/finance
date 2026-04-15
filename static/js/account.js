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

    function buildProfileImageUrl(imagePath) {
        const path = String(imagePath || '').trim();

        if (!path) {
            return '';
        }

        return `/${path.replace(/^\/+/, '')}`;
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
                image.src = buildProfileImageUrl(imagePath);
                image.hidden = false;
                fallback.hidden = true;
            } else {
                image.removeAttribute('src');
                image.hidden = true;
                fallback.hidden = false;
            }
        }
    }

    function fillForm(user) {
        const usernameInput = document.getElementById('account-username');
        const emailInput = document.getElementById('account-email');

        if (usernameInput) {
            usernameInput.value = user.username || '';
        }

        if (emailInput) {
            emailInput.value = user.email || '';
        }
    }

    function updatePictureStatus(message, kind = '') {
        const statusNode = document.getElementById('account-picture-status');

        if (!statusNode) {
            return;
        }

        statusNode.textContent = message || '';
        statusNode.classList.remove('is-success', 'is-error');

        if (kind) {
            statusNode.classList.add(kind);
        }
    }

    function clearPictureSelection(elements) {
        const {
            pictureInput,
            pictureFileName,
            picturePreview,
            picturePreviewImage,
            pictureUploadButton,
        } = elements;

        if (pictureInput) {
            pictureInput.value = '';
        }

        if (pictureFileName) {
            pictureFileName.textContent = 'No file selected';
        }

        if (picturePreview) {
            picturePreview.hidden = true;
        }

        if (picturePreviewImage) {
            picturePreviewImage.removeAttribute('src');
        }

        if (pictureUploadButton) {
            pictureUploadButton.disabled = true;
        }
    }

    function setPictureSelection(elements, file) {
        const {
            pictureFileName,
            picturePreview,
            picturePreviewImage,
            pictureUploadButton,
        } = elements;

        if (pictureFileName) {
            pictureFileName.textContent = file ? file.name : 'No file selected';
        }

        if (!file) {
            clearPictureSelection(elements);
            return;
        }

        if (picturePreview) {
            picturePreview.hidden = false;
        }

        if (pictureUploadButton) {
            pictureUploadButton.disabled = false;
        }

        const reader = new FileReader();
        reader.addEventListener('load', () => {
            if (picturePreviewImage) {
                picturePreviewImage.src = String(reader.result || '');
            }
        });
        reader.readAsDataURL(file);
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

        const latestUser = await window.get_current_user({ forceRefresh: true });
        if (latestUser) {
            user = latestUser;
        }
        const pictureInput = document.getElementById('account-picture-input');
        const pictureChooseButton = document.getElementById('account-picture-choose-button');
        const pictureUploadButton = document.getElementById('account-picture-upload-button');
        const pictureFileName = document.getElementById('account-picture-file-name');
        const picturePreview = document.getElementById('account-picture-preview');
        const picturePreviewImage = document.getElementById('account-picture-preview-image');
        const uploadDefaultText = pictureUploadButton ? pictureUploadButton.textContent : 'Upload Picture';
        const pictureElements = {
            pictureInput,
            pictureFileName,
            picturePreview,
            picturePreviewImage,
            pictureUploadButton,
        };
        let selectedPictureFile = null;

        setSidebarLinks(user.id);
        fillForm(user);
        updateProfilePreview(user);
        clearPictureSelection(pictureElements);
        updatePictureStatus('');

        if (pictureChooseButton && pictureInput) {
            pictureChooseButton.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    pictureInput.click();
                }
            });
        }

        if (pictureInput) {
            pictureInput.addEventListener('change', () => {
                const file = pictureInput.files && pictureInput.files[0] ? pictureInput.files[0] : null;

                if (!file) {
                    selectedPictureFile = null;
                    clearPictureSelection(pictureElements);
                    updatePictureStatus('');
                    return;
                }

                if (file.type && !file.type.startsWith('image/')) {
                    selectedPictureFile = null;
                    clearPictureSelection(pictureElements);
                    updatePictureStatus('Please choose an image file.', 'is-error');
                    return;
                }

                selectedPictureFile = file;
                setPictureSelection(pictureElements, file);
                updatePictureStatus('Preview ready. Upload when you are ready.');
            });
        }

        if (pictureUploadButton) {
            pictureUploadButton.addEventListener('click', async () => {
                if (!selectedPictureFile) {
                    updatePictureStatus('Choose an image before uploading.', 'is-error');
                    return;
                }

                const uploadButtonText = pictureUploadButton.textContent;
                pictureUploadButton.disabled = true;
                pictureUploadButton.textContent = 'Uploading...';
                updatePictureStatus('Uploading profile picture...');

                try {
                    const formData = new FormData();
                    formData.append('file', selectedPictureFile);

                    const response = await fetch(`/api/users/${user.id}/picture`, {
                        method: 'PATCH',
                        headers: {
                            Authorization: `Bearer ${token}`,
                        },
                        body: formData,
                    });

                    if (response.status === 401) {
                        window.location.assign('/login');
                        return;
                    }

                    const body = await response.json().catch(() => ({}));

                    if (response.status === 403) {
                        updatePictureStatus(window.parseApiError(body, 'You are not allowed to update this profile picture.'), 'is-error');
                        return;
                    }

                    if (!response.ok) {
                        updatePictureStatus(window.parseApiError(body, 'Unable to upload profile picture.'), 'is-error');
                        return;
                    }

                    window.invalidateCurrentUserCache();
                    user = body;
                    token = window.getStoredToken() || token;
                    fillForm(user);
                    updateProfilePreview(user);
                    selectedPictureFile = null;
                    clearPictureSelection(pictureElements);
                    updatePictureStatus('Profile picture uploaded successfully.', 'is-success');
                    await window.updateAuthUI();
                } catch (error) {
                    updatePictureStatus('Unable to upload profile picture.', 'is-error');
                } finally {
                    if (pictureUploadButton) {
                        pictureUploadButton.textContent = uploadButtonText || uploadDefaultText;
                        pictureUploadButton.disabled = !selectedPictureFile;
                    }
                }
            });
        }

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
                username: usernameValue,
                email: emailValue,
                phone_no: user.phone_no || null,
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

        const changePasswordForm = document.getElementById('changePasswordForm');
        if (changePasswordForm) {
            changePasswordForm.addEventListener('submit', async (event) => {
                event.preventDefault();

                if (!changePasswordForm.checkValidity()) {
                    changePasswordForm.reportValidity();
                    return;
                }

                const currentPassword = String(document.getElementById('changePasswordCurrent')?.value || '').trim();
                const newPassword = String(document.getElementById('changePasswordNew')?.value || '').trim();
                const confirmPassword = String(document.getElementById('changePasswordConfirm')?.value || '').trim();

                if (!currentPassword || !newPassword || !confirmPassword) {
                    modal.info('All fields are required.', 'Validation error');
                    return;
                }

                if (newPassword !== confirmPassword) {
                    modal.info('New passwords do not match.', 'Validation error');
                    return;
                }

                const messageElement = document.getElementById('changePasswordMessage');
                if (messageElement) {
                    messageElement.textContent = '';
                    messageElement.className = 'auth-message';
                }

                const submitButton = changePasswordForm.querySelector('button[type="submit"]');
                if (submitButton) {
                    submitButton.disabled = true;
                }

                try {
                    const response = await fetch('/api/users/me/password', {
                        method: 'PATCH',
                        headers: {
                            Authorization: `Bearer ${token}`,
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            current_password: currentPassword,
                            new_password: newPassword,
                        }),
                    });

                    if (response.status === 401) {
                        window.location.assign('/login');
                        return;
                    }

                    const body = await response.json().catch(() => ({}));

                    if (!response.ok) {
                        const errorMessage = window.parseApiError(body, 'Unable to change password. Please verify your current password and try again.');
                        if (messageElement) {
                            messageElement.textContent = errorMessage;
                            messageElement.classList.add('is-error');
                        }
                        return;
                    }

                    // Success
                    if (messageElement) {
                        messageElement.textContent = 'Password changed successfully!';
                        messageElement.classList.add('is-success');
                    }

                    // Clear the form
                    changePasswordForm.reset();

                    // Clear message after 3 seconds
                    setTimeout(() => {
                        if (messageElement) {
                            messageElement.textContent = '';
                            messageElement.className = 'auth-message';
                        }
                    }, 3000);
                } catch (error) {
                    if (messageElement) {
                        messageElement.textContent = 'An error occurred. Please try again.';
                        messageElement.classList.add('is-error');
                    }
                } finally {
                    if (submitButton) {
                        submitButton.disabled = false;
                    }
                }
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
