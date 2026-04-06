// Package v1 defines the FlightRoute custom resource schema.
//
// A FlightRoute models an aviation route (e.g. LHR-JFK) and declares
// the minimum replica count and SLO target for the services backing it.
// The operator ensures services never drift below minReplicas.
package v1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"sigs.k8s.io/controller-runtime/pkg/scheme"
)

// GroupVersion is the group and version for this API.
var (
	GroupVersion  = schema.GroupVersion{Group: "ops.kumarrajapuvvalla-bit.github.io", Version: "v1"}
	SchemeBuilder = &scheme.Builder{GroupVersion: GroupVersion}
	AddToScheme   = SchemeBuilder.AddToScheme
)

// FlightRouteSpec defines the desired state of a FlightRoute.
type FlightRouteSpec struct {
	// RouteCode is the IATA route identifier, e.g. LHR-JFK.
	// +kubebuilder:validation:Pattern=`^[A-Z]{3}-[A-Z]{3}$`
	RouteCode string `json:"routeCode"`

	// TargetDeployment is the name of the Deployment this route's traffic is served by.
	TargetDeployment string `json:"targetDeployment"`

	// MinReplicas is the minimum number of pod replicas the operator will enforce.
	// If the Deployment falls below this, the operator scales it back up.
	// +kubebuilder:validation:Minimum=1
	MinReplicas int32 `json:"minReplicas"`

	// SloTarget is the availability target as a percentage, e.g. 99.9.
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:validation:Maximum=100
	SloTarget float64 `json:"sloTarget"`

	// HealingEnabled controls whether the operator will auto-scale the deployment.
	// Set to false to observe only (useful during incidents).
	// +optional
	HealingEnabled *bool `json:"healingEnabled,omitempty"`
}

// FlightRouteStatus describes the observed state of a FlightRoute.
type FlightRouteStatus struct {
	// CurrentReplicas is the last observed replica count of the target deployment.
	// +optional
	CurrentReplicas int32 `json:"currentReplicas,omitempty"`

	// LastHealedAt is the timestamp of the most recent self-healing action.
	// +optional
	LastHealedAt *metav1.Time `json:"lastHealedAt,omitempty"`

	// HealingCount is the total number of self-healing actions taken.
	// +optional
	HealingCount int64 `json:"healingCount,omitempty"`

	// Conditions holds the standard Kubernetes condition array.
	// +optional
	Conditions []metav1.Condition `json:"conditions,omitempty"`

	// SloCompliant indicates whether current behaviour meets the declared SLO target.
	// +optional
	SloCompliant bool `json:"sloCompliant,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:printcolumn:name="Route",type=string,JSONPath=`.spec.routeCode`
// +kubebuilder:printcolumn:name="MinReplicas",type=integer,JSONPath=`.spec.minReplicas`
// +kubebuilder:printcolumn:name="Current",type=integer,JSONPath=`.status.currentReplicas`
// +kubebuilder:printcolumn:name="SLO",type=number,JSONPath=`.spec.sloTarget`
// +kubebuilder:printcolumn:name="Healed",type=integer,JSONPath=`.status.healingCount`

// FlightRoute is the Schema for the flightroutes API.
type FlightRoute struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   FlightRouteSpec   `json:"spec,omitempty"`
	Status FlightRouteStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// FlightRouteList contains a list of FlightRoute.
type FlightRouteList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []FlightRoute `json:"items"`
}

func init() {
	SchemeBuilder.Register(&FlightRoute{}, &FlightRouteList{})
}
