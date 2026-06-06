#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
物理实验CCA评估器主文件

整合所有评估指标，提供统一的评估接口
"""

import json
import time
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from .physics_cca_metrics import (
    PhysicsCCAMetricsCalculator, 
    PhysicsCCAMetrics,
    calculate_all_metrics
)


class PhysicsCCAEvaluator:
    """
    物理实验CCA评估器
    
    功能：
    1. 加载物理实验知识图谱
    2. 计算三维度六指标
    3. 生成评估报告
    4. 提供改进建议
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化评估器
        
        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.calculator = PhysicsCCAMetricsCalculator(config)
        self.evaluation_history: List[PhysicsCCAMetrics] = []
        
        # 知识更新历史（用于KER计算）
        self.knowledge_update_history: List[Dict] = []
        
        # 过期知识清除历史（用于OKCR计算）
        self.expired_knowledge_history: List[Dict] = []
    
    def load_knowledge_graph(self, kg_path: str) -> Dict[str, Any]:
        """
        加载知识图谱JSON文件
        
        Args:
            kg_path: 知识图谱文件路径
        
        Returns:
            知识图谱字典
        """
        with open(kg_path, 'r', encoding='utf-8') as f:
            kg = json.load(f)
        
        # 兼容两种格式
        if "entities" not in kg:
            # 如果是experiments.json格式，需要转换
            kg = self._convert_experiments_format(kg)
        
        return kg
    
    def _convert_experiments_format(self, experiments_data: Dict[str, Any]) -> Dict[str, Any]:
        """将experiments.json格式转换为标准KG格式"""
        entities = {}
        relations = []
        
        exp_counter = 0
        inst_counter = 0
        step_counter = 0
        rel_counter = 0
        
        for exp in experiments_data.get("experiments", []):
            exp_data = exp["data"]
            exp_name = exp_data["name"]
            
            # 实验实体
            exp_id = f"exp_{exp_counter:04d}"
            entities[exp_id] = {
                "id": exp_id,
                "name": exp_name,
                "type": "concept",
                "attributes": {
                    "purpose": exp_data.get("purpose", ""),
                    "theory": exp_data.get("theory", "")
                }
            }
            exp_counter += 1
            
            # 仪器实体和关系
            for eq in exp_data.get("equipment", []):
                eq_name = eq.get("name", "")
                if eq_name:
                    inst_id = f"inst_{inst_counter:04d}"
                    entities[inst_id] = {
                        "id": inst_id,
                        "name": eq_name,
                        "type": "instrument",
                        "attributes": {"quantity": eq.get("quantity", 1)}
                    }
                    relations.append({
                        "id": f"rel_{rel_counter:04d}",
                        "source_id": exp_id,
                        "source_name": exp_name,
                        "target_id": inst_id,
                        "target_name": eq_name,
                        "type": "contains",
                        "confidence": 0.9
                    })
                    inst_counter += 1
                    rel_counter += 1
            
            # 步骤实体和关系
            for step_idx, step in enumerate(exp_data.get("steps", [])):
                if step and len(step) > 5:
                    step_id = f"step_{step_counter:04d}"
                    step_name = step[:50] if len(step) > 50 else step
                    entities[step_id] = {
                        "id": step_id,
                        "name": step_name,
                        "type": "procedure",
                        "attributes": {"order": step_idx, "full_text": step}
                    }
                    relations.append({
                        "id": f"rel_{rel_counter:04d}",
                        "source_id": exp_id,
                        "source_name": exp_name,
                        "target_id": step_id,
                        "target_name": step_name,
                        "type": "contains",
                        "confidence": 0.85
                    })
                    step_counter += 1
                    rel_counter += 1
        
        return {
            "metadata": {
                "converted_from": "experiments.json",
                "original_experiments": exp_counter
            },
            "entities": entities,
            "relations": relations,
            "rules": []
        }
    
    def evaluate(self, kg: Dict[str, Any]) -> PhysicsCCAMetrics:
        """
        执行完整评估
        
        Args:
            kg: 知识图谱数据
        
        Returns:
            PhysicsCCAMetrics对象
        """
        start_time = time.time()
        
        metrics = calculate_all_metrics(
            kg,
            history=self.knowledge_update_history,
            expired_history=self.expired_knowledge_history,
            config=self.config
        )
        
        # 记录评估历史
        self.evaluation_history.append(metrics)
        
        elapsed = time.time() - start_time
        
        # 添加元数据
        metrics.metadata = {
            "evaluation_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "evaluation_duration": round(elapsed, 2)
        }
        
        return metrics
    
    def evaluate_from_file(self, kg_path: str) -> PhysicsCCAMetrics:
        """从文件加载知识图谱并评估"""
        kg = self.load_knowledge_graph(kg_path)
        return self.evaluate(kg)
    
    def record_update(self, added: int = 0, updated: int = 0):
        """记录知识更新（用于KER计算）"""
        self.knowledge_update_history.append({
            "timestamp": time.time(),
            "added": added,
            "updated": updated
        })
        
        # 保留最近100条记录
        if len(self.knowledge_update_history) > 100:
            self.knowledge_update_history = self.knowledge_update_history[-100:]
    
    def record_clearance(self, expired_count: int = 0, cleared_count: int = 0):
        """记录过期知识清除（用于OKCR计算）"""
        self.expired_knowledge_history.append({
            "timestamp": time.time(),
            "expired_count": expired_count,
            "cleared_count": cleared_count
        })
        
        # 保留最近100条记录
        if len(self.expired_knowledge_history) > 100:
            self.expired_knowledge_history = self.expired_knowledge_history[-100:]
    
    def get_grade(self, metrics: PhysicsCCAMetrics) -> Tuple[str, str]:
        """获取评级"""
        return metrics.get_grade()
    
    def generate_recommendations(self, metrics: PhysicsCCAMetrics) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        thresholds = self.calculator.thresholds
        
        if metrics.ocr > thresholds["ocr_max"]:
            recommendations.append(
                f"本体冲突率过高 ({metrics.ocr:.3f} > {thresholds['ocr_max']})，"
                "建议检查实体类型定义和关系约束一致性"
            )
        
        if metrics.pcr < thresholds["pcr_min"]:
            recommendations.append(
                f"路径连贯性不足 ({metrics.pcr:.3f} < {thresholds['pcr_min']})，"
                "建议补充实验之间的知识关联，构建更完整的知识网络"
            )
        
        if metrics.pmc < thresholds["pmc_min"]:
            recommendations.append(
                f"原型匹配度偏低 ({metrics.pmc:.3f} < {thresholds['pmc_min']})，"
                "建议对照物理实验标准模板完善实体特征"
            )
        
        if metrics.cec < thresholds["cec_min"]:
            recommendations.append(
                f"认知经济度偏低 ({metrics.cec:.3f} < {thresholds['cec_min']})，"
                "建议优化知识表示，去除冗余信息"
            )
        
        if metrics.ker < thresholds["ker_min"]:
            recommendations.append(
                f"知识演化率偏低 ({metrics.ker:.3f} < {thresholds['ker_min']})，"
                "建议加快知识更新频率，及时纳入新实验数据"
            )
        
        if metrics.okcr < thresholds["okcr_min"]:
            recommendations.append(
                f"过时知识清除率偏低 ({metrics.okcr:.3f} < {thresholds['okcr_min']})，"
                "建议建立定期审核机制，及时淘汰过期知识"
            )
        
        if not recommendations:
            recommendations.append("知识质量良好，建议继续保持并定期更新")
        
        return recommendations
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取评估统计信息"""
        if not self.evaluation_history:
            return {"message": "暂无评估历史"}
        
        latest = self.evaluation_history[-1]
        
        return {
            "total_evaluations": len(self.evaluation_history),
            "latest_evaluation": {
                "time": getattr(latest, 'metadata', {}).get('evaluation_time', '未知'),
                "overall": latest.overall,
                "grade": self.get_grade(latest)[1]
            },
            "update_history": {
                "total_updates": len(self.knowledge_update_history),
                "total_clearances": len(self.expired_knowledge_history)
            }
        }


# 便捷函数
def evaluate_physics_kg(kg_path: str) -> PhysicsCCAMetrics:
    """评估物理实验知识图谱的便捷函数"""
    evaluator = PhysicsCCAEvaluator()
    return evaluator.evaluate_from_file(kg_path)
