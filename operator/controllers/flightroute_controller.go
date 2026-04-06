// Package controllers implements the FlightRoute reconciliation loop.
package controllers

import (
	"context"
	"fmt"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/tools/record"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"

	opsv1 "github.com/kumarrajapuvvalla-bit/ops-platform/operator/api/v1"
)

// FlightRouteReconciler reconciles FlightRoute objects.
type FlightRouteReconciler struct {
	client.Client
	Scheme   *runtime.Scheme
	Recorder record.EventRecorder
}

// +kubebuilder:rbac:groups=ops.kumarrajapuvvalla-bit.github.io,resources=flightroutes,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=ops.kumarrajapuvvalla-bit.github.io,resources=flightroutes/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=apps,resources=deployments,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=core,resources=events,verbs=create;patch

// Reconcile is the core controller-runtime reconciliation loop.
// It is called whenever a FlightRoute or its watched Deployment changes.
func (r *FlightRouteReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.FromContext(ctx)

	// Fetch the FlightRoute instance
	var flightRoute opsv1.FlightRoute
	if err := r.Get(ctx, req.NamespacedName, &flightRoute); err != nil {
		if errors.IsNotFound(err) {
			// Resource deleted — nothing to do
			return ctrl.Result{}, nil
		}
		return ctrl.Result{}, fmt.Errorf("get FlightRoute: %w", err)
	}

	logger.Info("Reconciling FlightRoute",
		"route", flightRoute.Spec.RouteCode,
		"minReplicas", flightRoute.Spec.MinReplicas,
	)

	// Fetch the target Deployment
	var deployment appsv1.Deployment
	deploymentKey := types.NamespacedName{
		Name:      flightRoute.Spec.TargetDeployment,
		Namespace: flightRoute.Namespace,
	}
	if err := r.Get(ctx, deploymentKey, &deployment); err != nil {
		if errors.IsNotFound(err) {
			logger.Info("Target deployment not found — requeuing",
				"deployment", flightRoute.Spec.TargetDeployment,
			)
			return ctrl.Result{RequeueAfter: 30 * time.Second}, nil
		}
		return ctrl.Result{}, fmt.Errorf("get Deployment: %w", err)
	}

	currentReplicas := *deployment.Spec.Replicas
	minReplicas := flightRoute.Spec.MinReplicas

	// Update status with current replica count
	flightRoute.Status.CurrentReplicas = currentReplicas

	// Check if healing is needed
	if currentReplicas < minReplicas {
		healingEnabled := flightRoute.Spec.HealingEnabled == nil || *flightRoute.Spec.HealingEnabled

		if healingEnabled {
			logger.Info("Drift detected — initiating self-healing",
				"route", flightRoute.Spec.RouteCode,
				"current", currentReplicas,
				"required", minReplicas,
			)

			if err := r.healDeployment(ctx, &flightRoute, &deployment, minReplicas); err != nil {
				return ctrl.Result{}, err
			}
		} else {
			logger.Info("Drift detected but healing disabled — observe only",
				"route", flightRoute.Spec.RouteCode,
			)
		}
		flightRoute.Status.SloCompliant = false
	} else {
		flightRoute.Status.SloCompliant = true
	}

	// Update status
	if err := r.Status().Update(ctx, &flightRoute); err != nil {
		return ctrl.Result{}, fmt.Errorf("update FlightRoute status: %w", err)
	}

	// Requeue every 30s to continuously monitor drift
	return ctrl.Result{RequeueAfter: 30 * time.Second}, nil
}

// SetupWithManager registers the controller with the manager.
func (r *FlightRouteReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&opsv1.FlightRoute{}).
		Owns(&appsv1.Deployment{}).
		Complete(r)
}
