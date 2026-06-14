from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

from app.schemas import ProductRecommendation


@dataclass
class CollaborativeRecommender:
    user_to_index: dict[str, int]
    item_ids: list[str]
    item_names: dict[str, str | None]
    user_factors: np.ndarray
    item_factors: np.ndarray
    user_seen_items: dict[str, set[str]]
    popular_items: list[str]

    @classmethod
    def fit(cls, transactions: pd.DataFrame, n_components: int = 50):
        interaction_frame = transactions.copy()
        interaction_frame["customer_id"] = interaction_frame["customer_id"].astype(str)
        interaction_frame["stock_code"] = interaction_frame["stock_code"].astype(str)
        interaction_frame["quantity"] = pd.to_numeric(interaction_frame["quantity"], errors="coerce").fillna(1)

        user_ids = sorted(interaction_frame["customer_id"].unique())
        item_ids = sorted(interaction_frame["stock_code"].unique())
        user_to_index = {user_id: index for index, user_id in enumerate(user_ids)}
        item_to_index = {item_id: index for index, item_id in enumerate(item_ids)}

        rows = interaction_frame["customer_id"].map(user_to_index).to_numpy()
        columns = interaction_frame["stock_code"].map(item_to_index).to_numpy()
        values = np.log1p(interaction_frame["quantity"].clip(lower=1).to_numpy(dtype=float))
        matrix = sparse.coo_matrix((values, (rows, columns)), shape=(len(user_ids), len(item_ids))).tocsr()

        max_components = max(1, min(n_components, min(matrix.shape) - 1))
        svd = TruncatedSVD(n_components=max_components, random_state=42)
        user_factors = svd.fit_transform(matrix)
        item_factors = svd.components_.T
        item_factors = normalize(item_factors)

        descriptions = (
            interaction_frame.dropna(subset=["stock_code"])
            .drop_duplicates("stock_code")
            .set_index("stock_code")
            .get("description", pd.Series(dtype=str))
        )
        item_names = {item_id: descriptions.get(item_id) for item_id in item_ids}
        popular_items = (
            interaction_frame.groupby("stock_code")["quantity"].sum().sort_values(ascending=False).index.astype(str).tolist()
        )
        user_seen_items = {
            user_id: set(group["stock_code"].astype(str))
            for user_id, group in interaction_frame.groupby("customer_id")
        }

        return cls(
            user_to_index=user_to_index,
            item_ids=item_ids,
            item_names=item_names,
            user_factors=user_factors,
            item_factors=item_factors,
            user_seen_items=user_seen_items,
            popular_items=popular_items,
        )

    def recommend(
        self,
        customer_id: str | None,
        recent_product_ids: list[str],
        top_n: int,
        include_seen: bool = False,
    ) -> list[ProductRecommendation]:
        scores = self._score_items(customer_id, recent_product_ids)
        seen = set()
        if customer_id and not include_seen:
            seen.update(self.user_seen_items.get(str(customer_id), set()))
        if not include_seen:
            seen.update(str(product_id) for product_id in recent_product_ids)

        ranked_indices = np.argsort(scores)[::-1]
        recommendations: list[ProductRecommendation] = []
        for index in ranked_indices:
            product_id = self.item_ids[index]
            if product_id in seen:
                continue
            recommendations.append(
                ProductRecommendation(
                    product_id=product_id,
                    score=round(float(scores[index]), 4),
                    name=self.item_names.get(product_id),
                )
            )
            if len(recommendations) >= top_n:
                return recommendations

        for product_id in self.popular_items:
            if product_id in seen or any(item.product_id == product_id for item in recommendations):
                continue
            recommendations.append(
                ProductRecommendation(product_id=product_id, score=0.0, name=self.item_names.get(product_id))
            )
            if len(recommendations) >= top_n:
                break

        return recommendations

    def _score_items(self, customer_id: str | None, recent_product_ids: list[str]) -> np.ndarray:
        if customer_id and str(customer_id) in self.user_to_index:
            user_index = self.user_to_index[str(customer_id)]
            return self.user_factors[user_index] @ self.item_factors.T

        known_recent_indices = [
            self.item_ids.index(str(product_id))
            for product_id in recent_product_ids
            if str(product_id) in self.item_ids
        ]
        if known_recent_indices:
            profile = self.item_factors[known_recent_indices].mean(axis=0)
            return profile @ self.item_factors.T

        popularity_scores = np.zeros(len(self.item_ids), dtype=float)
        for rank, product_id in enumerate(self.popular_items):
            popularity_scores[self.item_ids.index(product_id)] = len(self.popular_items) - rank
        return popularity_scores
