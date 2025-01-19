# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GyazoUploaderDialog
                                 A QGIS plugin
 Plug-in to upload QGIS maps to Gyazo
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2025-01-18
        git sha              : $Format:%H$
        copyright            : (C) 2025 by yuiseki
        email                : yuiseki@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets, QtGui, QtCore
from qgis.PyQt.QtCore import QTranslator, QCoreApplication, QUrl, QUrlQuery, QByteArray
from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkAccessManager, QHttpMultiPart, QHttpPart
from .gyazo_oauth_handler import GyazoOAuthHandler
from dotenv import load_dotenv


# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'gyazo_uploader_dialog_base.ui'))

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

class GyazoUploaderDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(GyazoUploaderDialog, self).__init__(parent)

        # Store the QGIS interface
        self.iface = iface

        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.setFixedSize(600, 450)

        # Main layout for the dialog
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        image = self.get_image()

        # Calculate the aspect ratio of the map view
        map_width = image.width()
        map_height = image.height()
        aspect_ratio = map_width / map_height

        # Determine QLabel size to maintain aspect ratio
        max_width = 580  # Maximum width for the image label
        max_height = 400  # Maximum height for the image label

        if max_width / aspect_ratio <= max_height:
            label_width = max_width
            label_height = max_width / aspect_ratio
        else:
            label_width = max_height * aspect_ratio
            label_height = max_height

        # Create a QLabel to display the image
        self.image_label = QtWidgets.QLabel(self)
        self.image_label.setFixedSize(int(label_width), int(label_height))

        # Convert QImage to QPixmap and set it to the QLabel
        pixmap = QtGui.QPixmap.fromImage(image)
        self.image_label.setPixmap(pixmap)
        self.image_label.setScaledContents(True)

        # Center the QLabel in the layout
        layout.addWidget(self.image_label, alignment=QtCore.Qt.AlignCenter)

        upload_button = QtWidgets.QPushButton(self.tr("Upload to Gyazo"))
        cancel_button = QtWidgets.QPushButton(self.tr("Cancel"))

        # Create a horizontal layout for the buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(upload_button)
        button_layout.addWidget(cancel_button)

        # Add the button layout to the main layout
        layout.addLayout(button_layout)

        # Connect the buttons to their respective slots
        upload_button.clicked.connect(self.upload_action)
        cancel_button.clicked.connect(self.reject)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('GyazoUploaderDialogBase', message)

    def get_image(self):
        """Capture the current map view as an image."""
        canvas = self.iface.mapCanvas()
        image = canvas.grab().toImage()
        return image

    def get_image_png(self):
        """Capture the current map view as png image bytes."""
        image = self.get_image()
        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        image_bytes = buffer.data().data()
        if not image_bytes:
            raise Exception("Image data is empty. Unable to upload.")
        return image_bytes

    def is_png_format(self, imagedata):
        png_signature = b'\x89PNG\r\n\x1a\n'
        return imagedata.startswith(png_signature)

    def oauth_action(self):
        """Run the OAuth flow to authenticate and upload."""
        auth_manager = QgsApplication.authManager()
        if not auth_manager.masterPasswordIsSet():
            auth_manager.setMasterPassword(True)

        auth_cfg_id = 'gyazo_upload_auth_config'

        auth_cfg = QgsAuthMethodConfig()
        (res, auth_cfg) = auth_manager.loadAuthenticationConfig(auth_cfg_id, auth_cfg, True)

        if res:
            saved_token = auth_cfg.configMap().get('token')
            return

        # Gyazo OAuth configuration
        self.client_id = os.getenv("GYAZO_CLIENT_ID")
        QtWidgets.QMessageBox.information(
            self, "Gyazo OAuth", f"client_id: {self.client_id}"
        )
        self.client_secret = os.getenv("GYAZO_CLIENT_SECRET")
        self.redirect_uri = "http://localhost:8080"
        self.scope = "upload"

        try:
            oauth_handler = GyazoOAuthHandler(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=self.scope,
            )
            access_token = oauth_handler.start_auth_flow()
            # Save the access token to the authentication manager
            auth_cfg.setId(auth_cfg_id)
            auth_cfg.setName("Gyazo OAuth Access Token")
            auth_cfg.setMethod("OAuth2")
            auth_cfg.setConfigMap({"token": access_token})
            auth_manager.storeAuthenticationConfig(auth_cfg, True)
            return auth_cfg
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "認証エラー", f"認証に失敗しました: {e}"
            )

    def upload_to_gyazo(self, saved_token):
        """Upload image to Gyazo."""
        url = 'https://upload.gyazo.com/api/upload'

        # Get the image data (as bytes)
        imagedata_png = self.get_image_png()
        if not imagedata_png:
            QtWidgets.QMessageBox.critical(
                self, "エラー", "画像データが空です。"
            )
            return

        # Debugging: Display PNG information
        imagedata_png_len = len(imagedata_png)
        is_png = self.is_png_format(imagedata_png)
        if not is_png:
            QtWidgets.QMessageBox.critical(
                self, "エラー", "画像データがPNG形式ではありません。"
            )
            return

        # Create the multipart request
        multipart = QHttpMultiPart(QHttpMultiPart.FormDataType)

        # Add the image data part
        image_part = QHttpPart()
        image_part.setHeader(
            QNetworkRequest.ContentDispositionHeader,
            b'form-data; name="imagedata"; filename="image.png"'
        )
        image_part.setBody(imagedata_png)
        multipart.append(image_part)

        # Add the access token part
        token_part = QHttpPart()
        token_part.setHeader(
            QNetworkRequest.ContentDispositionHeader,
            b'form-data; name="access_token"'
        )
        token_part.setBody(saved_token.encode())
        multipart.append(token_part)

        # Create the network request
        request = QNetworkRequest(QUrl(url))

        # Send the request
        network_manager = QNetworkAccessManager(self)
        reply = network_manager.post(request, multipart)

        # Handle the reply asynchronously
        reply.finished.connect(lambda: self.handle_upload_reply(reply))

        # Ensure the multipart object is not garbage-collected
        multipart.setParent(reply)

    def handle_upload_reply(self, reply):
        """Handle the upload response."""
        if reply.error():
            # Retrieve the response body for debugging
            response_body = reply.readAll().data().decode()
            QtWidgets.QMessageBox.critical(
                self, 
                "アップロードエラー", 
                f"アップロードに失敗しました: {reply.errorString()}\n\nResponse Body:\n{response_body}"
            )
        else:
            gyazo_url = reply.readAll().data().decode()
            QtWidgets.QMessageBox.information(
                self, "アップロード完了", f"アップロードが完了しました: {gyazo_url}"
            )

    def upload_action(self):
        """Handle the upload action."""
        # Add your upload logic here
        print("アップロード処理を実行")
        auth_cfg_id = 'gyazo_upload_auth_config'
        auth_cfg = QgsAuthMethodConfig()
        auth_manager = QgsApplication.authManager()
        (res, auth_cfg) = auth_manager.loadAuthenticationConfig(auth_cfg_id, auth_cfg, True)
        if not res:
            auth_cfg = self.oauth_action()

        saved_token = auth_cfg.configMap().get('token')

        self.upload_to_gyazo(saved_token)
        self.accept()  # Close the dialog after upload
