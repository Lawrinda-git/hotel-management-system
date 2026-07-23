import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, FlatList, ActivityIndicator } from 'react-native';

const BookingScreen = ({ navigation }) => {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBookings();
  }, []);

  const fetchBookings = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/booking/options/');
      const data = await response.json();
      setBookings(data.results || []);
    } catch (error) {
      console.error('Failed to fetch bookings:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f7f9fb' }}>
        <ActivityIndicator size="large" color="#00288e" />
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: '#f7f9fb' }}>
      <View style={{ padding: 20 }}>
        <Text style={{ fontSize: 20, fontWeight: '600', color: '#00288e' }}>My Bookings</Text>
      </View>
      
      {bookings.length === 0 ? (
        <View style={{ padding: 20, alignItems: 'center' }}>
          <Text style={{ color: '#444653' }}>No bookings found</Text>
          <TouchableOpacity 
            style={{ backgroundColor: '#00288e', borderRadius: 12, padding: 16, marginTop: 16 }}
            onPress={() => navigation.navigate('Search')}
          >
            <Text style={{ color: '#ffffff' }}>Book a Room</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={bookings}
          keyExtractor={(item) => item.id.toString()}
          renderItem={({ item }) => (
            <View style={{
              backgroundColor: '#ffffff',
              marginHorizontal: 20,
              marginBottom: 12,
              borderRadius: 12,
              padding: 16,
              elevation: 1,
            }}>
              <Text style={{ fontSize: 16, fontWeight: '600', color: '#191c1e' }}>
                {item.room_type?.type_name} - Room {item.room_number}
              </Text>
              <Text style={{ color: '#444653' }}>{item.hotel?.hotel_name}</Text>
              <Text style={{ color: '#00288e', fontWeight: '600', marginTop: 8 }}>
                GH₵{item.room_type?.price_per_night}/night
              </Text>
            </View>
          )}
        />
      )}
    </View>
  );
};

export default BookingScreen;