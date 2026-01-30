    def draw_nodes_and_text_old(self, painter: QPainter):
        # ----------------------------画圆----------------------------
        scene = self.scene()
        views = scene.views() if scene is not None else []
        pos = self.state.pos
        neighbor_mask = None
        if (
            self.neighbor_mask is not None
            and self.neighbor_mask.shape[0] == self.state.pos.shape[0]
            and self.hover_index != -1
        ):
            neighbor_mask = self.neighbor_mask
            self._last_neighbor_mask = self.neighbor_mask

        painter.setPen(Qt.NoPen)# type: ignore[arg-type]

        for i in self.visible_indices:
            x, y = pos[i]
            r = self.show_radius[i]
            if self.hover_index != -1:
                if i == self.hover_index:
                    t = float(self._hover_global)
                    color = self._mix_color(self.base_color, self.hover_color, t)
                elif neighbor_mask is not None and neighbor_mask[i]:
                    color = self.base_color
                else:
                    t = float(self._hover_global)
                    color = self._mix_color(self.base_color, self.dim_color, t)
            else:
                if self._hover_global <= 0.0:
                    color = self.base_color
                else:
                    if i == self.last_hover_index:
                        t = float(self._hover_global)
                        color = self._mix_color(self.base_color, self.hover_color, t)
                    elif (
                        self._last_neighbor_mask is not None
                        and i < self._last_neighbor_mask.shape[0]
                        and self._last_neighbor_mask[i]
                    ):
                        color = self.base_color
                    else:
                        t = float(self._hover_global)
                        color = self._mix_color(self.base_color, self.dim_color, t)
            painter.setBrush(QBrush(color))
            if i == self.hover_index:
                r = r * 1.1
            painter.drawEllipse(QPointF(x, y), r, r)# type: ignore[arg-type] #循环绘图，当检测到是悬停点时，放大半径，修改颜色


        # ---------------------画文字-------------------------
        # 性能
        # LOD 当缩放过小时不绘制文本
        # 缓存文字的静态文本，避免重复创建
        # 体验
        # 当缩放在0.7-1时透明度变化
        # 在选中非选中的时候文字的颜色缓缓变化

        scale = 1.0
        if views:
            t = views[0].transform()
            scale = t.m11()

        if scale > self.textshreshold_off:
            prev_text_aa = painter.testRenderHint(QPainter.TextAntialiasing)# type: ignore[arg-type]
            if scale < 1.5:#当缩放比例小于1.5时，关闭文本抗锯齿
                painter.setRenderHint(QPainter.TextAntialiasing, False)# type: ignore[arg-type]
            factor = (scale - self.textshreshold_off) / (self.textshreshold_show - self.textshreshold_off)#这个factor是计算透明度的
            if factor > self.textshreshold_show:
                factor = 1.0
            base_alpha = int(255 * factor)
            for i in self.visible_indices:
                if i == self.hover_index :#这里绘制那些不需要动态计算的文字
                    continue
                x, y = pos[i]
                r = self.show_radius[i]
                text = str(self.labels[i])# type: ignore[arg-type]
                t = float(self._hover_global)
                if self.hover_index != -1:#整体有选中的状态
                    font = self.font
                    cache_item = self._static_text_cache.get(text)
                    if cache_item is None:
                        continue
                    static_text, w = cache_item
                    if neighbor_mask is not None and neighbor_mask[i]:
                        alpha_i = base_alpha
                    else:
                        fade = 1.0 - 0.7 * t
                        alpha_i = int(base_alpha * fade)
                else:#整体无选中的状态
                    if t <= 0.0:#无变化
                        font = self.font
                        cache_item = self._static_text_cache.get(text)
                        static_text, w = cache_item
                        alpha_i = base_alpha
                    else:
                        if i == self.last_hover_index:#上次悬停的节点
                            alpha_i = base_alpha
                            font = self.font
                            cache_item = self._static_text_cache.get(text)
                            static_text, w = cache_item
                            pass#这里暂时不做变化
                        else:
                            font = self.font
                            cache_item = self._static_text_cache.get(text)
                            if cache_item is None:
                                continue
                            static_text, w = cache_item
                            is_neighbor = (
                                self._last_neighbor_mask is not None
                                and i < self._last_neighbor_mask.shape[0]
                                and self._last_neighbor_mask[i]
                            )
                            if is_neighbor:
                                alpha_i = base_alpha
                            else:
                                fade = 1.0 - 0.7 * t
                                alpha_i = int(base_alpha * fade)

                cache_item = self._static_text_cache.get(text)
                if cache_item is None:
                    continue
                static_text, w = cache_item
                color = QColor("#5C5C5C")
                color.setAlpha(alpha_i)
                painter.setPen(QPen(color))
                painter.setFont(font)
                painter.drawStaticText(QPointF(x - w / 2, y + r), static_text)
  
            painter.setRenderHint(QPainter.TextAntialiasing, prev_text_aa)# type: ignore[arg-type]

        if self.hover_index != -1:# 绘制选中节点的文字（无视普通 LOD 规则）
            i = self.hover_index
            x, y = pos[i]
            r = self.show_radius[i]
            text = str(self.labels[i])# type: ignore[arg-type]
            t = float(self._hover_global)
            font = QFont(self.font)
            base_size = self.font.pointSizeF()
            if base_size <= 0:
                base_size = float(self.font.pointSize())

            # 选中文字比普通大一截；缩小时用 1/scale 抵消视图缩放，保持屏幕上大小基本不变

            target_size = base_size *(1+t * 2.0) 

            if 0.0 < scale <= 1.0:
                size_factor = 1.0 / scale 
            else:
                size_factor = 1.0 / (scale*2.0) +0.5

            font.setPointSizeF(target_size * size_factor)

            fm = QFontMetrics(font)
            w = fm.horizontalAdvance(text)
            rect = fm.boundingRect(text)
            color = QColor("#5C5C5C")
            painter.setPen(QPen(color))
            painter.setFont(font)
            # 在普通文字的基础上向下平移一段，使屏幕上的距离大致恒定
            # 这里按“一个鼠标高度”近似，用字体高度作为基准
            offset_y = (self.font_height * (0.2*t+1)) / scale
            y_base = y + r - rect.top() + offset_y
            painter.drawText(QPointF(x - w / 2, y_base), text)
