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
from qgis.PyQt.QtCore import QTranslator, QCoreApplication, QUrl, QUrlQuery, QByteArray, QRect
from qgis.core import QgsApplication, QgsAuthMethodConfig, QgsProject, QgsLayerTreeLayer
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkAccessManager, QHttpMultiPart, QHttpPart
from PyQt5.QtGui import QPainter, QImage, QColor, QFont
from gyazo_oauth_handler import GyazoOAuthHandler
import json
import webbrowser

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'gyazo_uploader_dialog_base.ui'))

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

        self.setFixedSize(600, 500)

        # Main layout for the dialog
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        image_bytes = self.get_image_png_with_attributions()
        image = QImage.fromData(image_bytes)

        # Calculate the aspect ratio of the map view
        map_width = image.width()
        map_height = image.height()
        aspect_ratio = map_width / map_height

        # Determine QLabel size to maintain aspect ratio
        max_width = 580  # Maximum width for the image label
        max_height = 450  # Maximum height for the image label

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

    def get_attributions(self):
        """Get the list of layers in the current project."""
        # プロジェクトのレイヤーツリーのルートを取得
        layer_tree_root = QgsProject.instance().layerTreeRoot()

        # 出典情報を格納するリスト
        attributions = []

        # レイヤーツリー内のすべてのレイヤーを取得
        for layer_tree_layer in layer_tree_root.findLayers():
            # レイヤーが可視状態であるかを確認
            if layer_tree_layer.isVisible():
                # 対応するレイヤーオブジェクトを取得
                layer = layer_tree_layer.layer()
                # 出典情報を取得
                attribution = layer.attribution()
                if attribution:
                    attributions.append(attribution)
                metadata = layer.metadata()
                layer_rights = metadata.rights()
                if layer_rights:
                    for rights in layer_rights:
                        attributions.append(rights)

        unique_attributions = list(set(attributions))
        return unique_attributions

    def get_image_with_attributions(self):
        """Capture the current map view as an image with attributions."""
        image = self.get_image()
        attributions = self.get_attributions()
        # 出典情報を結合して1つの文字列にまとめる
        attribution_text = " | ".join(attributions)

        # フォント設定
        font = QFont("Arial", 10)

        # テキストの高さを計算
        painter = QPainter()
        painter.begin(image)
        painter.setFont(font)
        text_rect = painter.boundingRect(QRect(0, 0, image.width(), 0), 0, attribution_text)
        text_height = text_rect.height()
        painter.end()

        # 新しい画像の高さを計算
        new_image_height = image.height() + text_height + 10  # 10ピクセルのマージンを追加

        # 新しい画像を作成
        new_image = QImage(image.width(), new_image_height, QImage.Format_ARGB32)
        new_image.fill(QColor(255, 255, 255))  # 白い背景

        # 新しい画像に元の地図を描画
        painter.begin(new_image)
        painter.drawImage(0, 0, image)

        # 出典情報を描画
        painter.setFont(font)
        painter.setPen(QColor(0, 0, 0))  # 黒色のテキスト
        painter.drawText(QRect(0, image.height() + 5, image.width(), text_height), 0, attribution_text)
        painter.end()

        return new_image

    def get_image_png_with_attributions(self):
        """Capture the current map view as png image bytes with attributions."""
        image = self.get_image_with_attributions()
        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        image_bytes = buffer.data().data()
        if not image_bytes:
            raise Exception("Image data is empty. Unable to upload.")
        return image_bytes

    def oauth_access_token(self):
        """Check if the Gyazo OAuth configuration exists."""
        auth_manager = QgsApplication.authManager()
        if not auth_manager.masterPasswordIsSet():
            auth_manager.setMasterPassword(True)

        auth_cfg_id = 'gyazo_upload_auth_config'
        auth_cfg = QgsAuthMethodConfig()
        (res, auth_cfg) = auth_manager.loadAuthenticationConfig(auth_cfg_id, auth_cfg, True)
        if not res:
            return None
        saved_access_token = auth_cfg.configMap().get('token')
        return saved_access_token

    def oauth_authorize(self):
        """Run the OAuth flow to authenticate and upload."""
        auth_manager = QgsApplication.authManager()
        if not auth_manager.masterPasswordIsSet():
            auth_manager.setMasterPassword(True)

        try:
            oauth_handler = GyazoOAuthHandler()
            access_token = oauth_handler.start_auth_flow()
            # Save the access token to the authentication manager
            auth_cfg_id = 'gyazo_upload_auth_config'
            auth_cfg = QgsAuthMethodConfig()
            auth_cfg.setId(auth_cfg_id)
            auth_cfg.setName("Gyazo OAuth Access Token")
            auth_cfg.setMethod("OAuth2")
            auth_cfg.setConfigMap({"token": access_token})
            auth_manager.storeAuthenticationConfig(auth_cfg, True)
            return access_token
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "認証エラー", f"認証に失敗しました: {e}"
            )

    def upload_to_gyazo(self, saved_token):
        """Upload image to Gyazo."""
        url = 'https://upload.gyazo.com/api/upload'

        imagedata_png = self.get_image_png_with_attributions()
        if not imagedata_png:
            return

        boundary = '----boundary123456'
        # 生のマルチパートデータを自前で作る
        body = []
        body.append(f'--{boundary}')
        body.append('Content-Disposition: form-data; name="imagedata"; filename="image.png"')
        body.append('Content-Type: image/png')
        body.append('')  # ヘッダ部とファイルバイナリの間は空行
        body_bytes = '\r\n'.join(body).encode('utf-8') + b'\r\n' + imagedata_png + b'\r\n'
        # app を追加
        body_bytes += f'--{boundary}\r\nContent-Disposition: form-data; name="app"\r\n\r\nGyazo for QGIS\r\n'.encode('utf-8')
        # 終端に access_token を追加
        body_tail = f'--{boundary}\r\nContent-Disposition: form-data; name="access_token"\r\n\r\n{saved_token}\r\n--{boundary}--\r\n'.encode('utf-8')
        final_body = body_bytes + body_tail

        request = QNetworkRequest(QUrl(url))
        # Content-Type を手動指定
        request.setHeader(QNetworkRequest.ContentTypeHeader, f'multipart/form-data; boundary={boundary}')
        # Content-Length も明示的に指定（これで chunked ではなくなる）
        request.setHeader(QNetworkRequest.ContentLengthHeader, str(len(final_body)))

        network_manager = QNetworkAccessManager(self)
        reply = network_manager.post(request, final_body)

        reply.finished.connect(lambda: self.handle_upload_reply(reply))

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
            gyazo_res = reply.readAll().data().decode()
            gyazo_json = json.loads(gyazo_res)
            gyazo_url = gyazo_json.get('permalink_url')
            webbrowser.open(gyazo_url)

    def upload_action(self):
        """Handle the upload action."""
        print("アクセストークンを取得")
        saved_access_token = self.oauth_access_token()
        if not saved_access_token:
            saved_access_token = self.oauth_authorize()
            if not saved_access_token:
                return
        print("アップロード処理を実行")
        self.upload_to_gyazo(saved_access_token)
        self.accept()  # Close the dialog after upload
