import pandas as pd
from io import BytesIO
from datetime import datetime
from typing import List, Dict, Any

class JournalExporter:
    """Экспорт журнала полётов в Excel и CSV."""

    COLUMNS = [
        "ID полёта", "БВС", "Статус", "Начало (план)", "Окончание (план)",
        "Начало (факт)", "Окончание (факт)", "Валидация", "Примечания"
    ]

    def _prepare_data(self, flights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = []
        for f in flights:
            verification = f.get("verification_result") or {}
            rows.append({
                "ID полёта": str(f.get("id", "")),
                "БВС": f.get("drone_name", f.get("drone_id", "")),
                "Статус": f.get("status", ""),
                "Начало (план)": f.get("scheduled_start", ""),
                "Окончание (план)": f.get("scheduled_end", ""),
                "Начало (факт)": f.get("actual_start", ""),
                "Окончание (факт)": f.get("actual_end", ""),
                "Валидация": "ПРОЙДЕНА" if verification.get("is_valid") else "КОНФЛИКТ",
                "Примечания": f.get("notes", "")
            })
        return rows

    def to_excel(self, flights: List[Dict[str, Any]]) -> BytesIO:
        df = pd.DataFrame(self._prepare_data(flights), columns=self.COLUMNS)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Журнал полётов")
            worksheet = writer.sheets["Журнал полётов"]
            for column in worksheet.columns:
                max_length = max(len(str(cell.value or "")) for cell in column)
                worksheet.column_dimensions[column[0].column_letter].width = min(max_length + 2, 50)
        buffer.seek(0)
        return buffer

    def to_csv(self, flights: List[Dict[str, Any]]) -> BytesIO:
        df = pd.DataFrame(self._prepare_data(flights), columns=self.COLUMNS)
        buffer = BytesIO()
        df.to_csv(buffer, index=False, encoding="utf-8-sig")
        buffer.seek(0)
        return buffer